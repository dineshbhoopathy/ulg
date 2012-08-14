#!/usr/bin/env python
#
# ULG - Universal Looking Glass
# by Tomas Hlavacek (tomas.hlavacek@nic.cz)
# last udate: June 21 2012
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Imports
import os
import re
from time import localtime, strftime
from genshi.template import TemplateLoader
from genshi.core import Markup
import pickle
import fcntl

import defaults



def log(*messages):
    try:
        with open(defaults.log_file, 'a') as l:
            for m in messages:
                l.write(strftime("%b %d %Y %H:%M:%S: ", localtime()) + m + "\n")
    except Exception:
        pass

def debug(message):
    log('DEBUG:' + message)


class PersistentStorage(object):
    def __init__(self):
        self.data = {}

    def save(self,filename=defaults.persistent_storage_file):
        # TODO: locking
        f = open(filename,'wb')
        pickle.dump(self, f)
        f.close()

    @staticmethod
    def load(filename=defaults.persistent_storage_file):
        # TODO: locking
        if(os.path.isfile(filename)):
            f = open(filename, 'rb')
            s = pickle.load(f)
            f.close()
            return s
        else:
            return PersistentStorage()

    def get(self,key):
        return self.data.get(key,None)

    def set(self,key,value):
        self.data[key] = value

    def delete(self,key):
        if(key in self.data.keys()):
            del(self.data[key])

    def getDict(self):
        return self.data

class TableDecorator(object):
    WHITE = '#FFFFFF'
    RED = '#FF0000'
    GREEN = '#00FF00'
    BLUE = '#0000FF'
    YELLOW = '#FFFF00'
    BLACK = '#000000'

    def __init__(self, table, table_header, table_headline=None, before=None, after=None):
        self.table = table
        self.table_header = table_header
        self.table_headline = table_headline
        self.before = before
        self.after = after

        self.loader=TemplateLoader(
            os.path.join(os.path.dirname(__file__), defaults.template_dir),
            auto_reload=True
            )

    def decorate(self):
        def preprocessTableCell(td):
            if(isinstance(td,(list,tuple))):
                if(len(td) >= 2):
                    return (Markup(str(td[0])),Markup(str(td[1])))
                elif(len(td) == 1):
                    return (Markup(str(td[0])),Markup(TableDecorator.WHITE))
                else:
                    return ('',Markup(TableDecorator.WHITE))
            else:
                return (Markup(str(td)),Markup(TableDecorator.WHITE))

        t = [[preprocessTableCell(td) for td in tr ] for tr in self.table]

        template = self.loader.load(defaults.table_decorator_template_file)
        return template.generate(table=t,
                                 table_header=self.table_header,
                                 table_headline=Markup(self.table_headline) if self.table_headline else '',
                                 before=Markup(self.before) if self.before else '',
                                 after=Markup(self.after) if self.after else '',
                                 ).render('html', doctype='html')


class TextParameter(object):
    def __init__(self,pattern='.*',name=defaults.STRING_PARAMETER,default=''):
        self.name=name
        self.pattern=pattern
        self.default=default

    def getType(self):
        return 'text'

    def getName(self):
        return self.name

    def getDefault(self):
        return self.default

    def checkInput(self,input):
        if(re.compile(self.pattern).match(input)):
            return True
        else:
            return False

    def normalizeInput(self,input):
        if(self.checkInput(input)):
            return input
        else:
            raise Exception("Invalid input encountered: Check did not passed.")


class SelectionParameter(TextParameter):
    def __init__(self,option_tuples=[],name=defaults.STRING_PARAMETER,default=None):
        "option_tupes=[(value,name),(value2,name2),(value3equalsname3,),...]"
        self.option_tuples = []
        self.setOptions(option_tuples)
        self.name=name
        self.default=default

    def getType(self):
        return 'select'

    def getDefault(self):
        if(self.default and (self.default in [v[0] for v in self.getOptions()])):
            return self.default
        else:
            return self.getOptions()[0]

    def setOptions(self,option_tuples):
        self.option_tuples = []
        for o in option_tuples:
            if(len(o) >= 2):
                self.option_tuples.append(tuple((o[0],o[1],)))
            elif(len(o) == 1):
                self.option_tuples.append(tuple((o[0],o[0],)))
            else:
                raise Exception("Invalid option passed in SelectionParameter configuration. Zero-sized tuple.")

    def getOptions(self):
        return self.option_tuples

    def checkInput(self,input):
        if(input and (input in [v[0] for v in self.getOptions()])):
            return True
        else:
            return False

    def normalizeInput(self,input):
        log("DEBUG: returning selection parameter input: "+str(input))
        if(self.checkInput(input)):
            return input
        else:
            raise Exception("Invalid input encountered: Check did not passed.")


class TextCommand(object):
    def __init__(self,command,param_specs=[],name=None):
        self.command=command
        self.param_specs=param_specs

        if(name==None):
            if(self.param_specs):
                self.name=command % tuple([('<'+str(c.getName())+'>') for c in self.param_specs])
            else:
                self.name=command
        else:
            self.name=name

    def getParamSpecs(self):
        return self.param_specs

    def getName(self):
        return self.name

    def checkParamsInput(self,input):
        if(((not input) and (self.getParamSpecs()))or((input) and (not self.getParamSpecs()))):
            log("Failed checking parameter count to zero, input:"+str(input)+' .')
            return False

        if(len(input)!=len(self.getParamSpecs())):
            log("Failed checking parameter count (nonzero), input: "+str(input)+' .')
            return False

        for pidx,p in enumerate(self.getParamSpecs()):
            if not p.checkInput(input[pidx]):
                log("Failed checking parameter: "+str(input[pidx]))
                return False

        return True

    def normalizeParameters(self,parameters):
        if parameters == None:
            return [] 
        else:
            return [self.getParamSpecs()[pidx].normalizeInput(p) for pidx,p in enumerate(parameters)]

    def getCommandText(self,parameters=None):
        if(self.checkParamsInput(parameters)):
            parameters_normalized = self.normalizeParameters(parameters)

            if(parameters_normalized):
                return self.command % tuple(parameters_normalized)
            else:
                return self.command

        else:
            return None

    def rescanHook(self,router):
        pass

    def decorateResult(self,result,router=None,decorator_helper=None):
        return "<pre>\n%s\n</pre>" % result
    
class AnyCommand(TextCommand):
    def __init__(self):
        self.command=''
        self.parameter = TextParameter('.+', name=defaults.STRING_COMMAND)
        self.name=defaults.STRING_ANY

    def getCommandText(self,parameters=None):
        c = ''

        parameters_normalized = self.normalizeParameters(parameters)
        if(len(parameters_normalized) == 0):
            raise Exception("Can not construct AnyCommand without valid parameter.")

        for p in parameters_normalized:
            c = c + ' ' + p

        return c

class Router(object):
    def __init__(self):
        self.setCommands([])
        self.setName('')

    def setName(self,name):
        self.name=name

    def getName(self):
        return self.name

    def setCommands(self, commands):
        self.commands=commands

    def listCommands(self):
        return self.commands

    def rescanHook(self):
        for c in self.listCommands():
            c.rescanHook(self)

    def returnError(self,error=None):
        r = '<em>'+defaults.STRING_ERROR_COMMANDRUN
        r = r + ': '+error+'</em>' if error else r+'.</em>'
        return r

    def runCommand(self,command,parameters,decorator_helper):
        c = command.getCommandText(parameters)

        if(c == None):
            log("Bad params encountered in command "+str(command.getName())+" : "+str(parameters))
            return self.returnError(defaults.STRING_BAD_PARAMS)

        r = ''
        if(defaults.debug):
            r = "<h3>DEBUG</h3><pre>Router.runCommand():\ncommand_name="+command.getName()+'\n'
            if(parameters != None):
                for pidx,p in enumerate(parameters):
                    r = r + " param"+str(pidx)+"="+str(p)+"\n"
            r = r + "complete command="+c+"\n" + \
                "</pre><hr>"

        r = r + command.decorateResult(self.runRawCommand(c),self,decorator_helper)
        return r

    def runRawCommand(self,command):
        """ Abstract method. """
        raise Exception("runRawCommand() method not supported for the abstract class Router. Inherit from the class and implement the method.")

    def getForkNeeded(self):
        return False

class RemoteRouter(Router):
    def getHost(self):
        return self.host

    def setHost(self,host):
        self.host = host

    def getPort(self):
        return self.port

    def setPort(self,port):
        self.port = port

    def getUser(self):
        return self.user

    def setUser(self,user):
        self.user = user

    def setPassword(self, password):
        self.password = password

class LocalRouter(Router):
    pass
