from .coin_api import *
from .cplex_api import  *
from .gurobi_api import *
from .glpk_api import *
from .choco_api import *
from .mipcl_api import *
from .mosek_api import *
from .scip_api import *
from .xpress_api import *
from .core import *

# Default solver selection
if PULP_CBC_CMD().available():
    LpSolverDefault = PULP_CBC_CMD()
elif GLPK_CMD().available():
    LpSolverDefault = GLPK_CMD()
elif COIN_CMD().available():
    LpSolverDefault = COIN_CMD()
else:
    LpSolverDefault = None

def setConfigInformation(**keywords):
    """
    set the data in the configuration file
    at the moment will only edit things in [locations]
    the keyword value pairs come from the keywords dictionary
    """
    #TODO: extend if we ever add another section in the config file
    #read the old configuration
    config = Parser()
    config.read(config_filename)
    #set the new keys
    for (key,val) in keywords.items():
        config.set("locations",key,val)
    #write the new configuration
    fp = open(config_filename,"w")
    config.write(fp)
    fp.close()


def configSolvers():
    """
    Configure the path the the solvers on the command line

    Designed to configure the file locations of the solvers from the
    command line after installation
    """
    configlist = [(cplex_dll_path, "cplexpath", "CPLEX: "),
                  (coinMP_path, "coinmppath", "CoinMP dll (windows only): ")]
    print("Please type the full path including filename and extension \n" +
          "for each solver available")
    configdict = {}
    for (default, key, msg) in configlist:
        value = input(msg + "[" + str(default) + "]")
        if value:
            configdict[key] = value
    setConfigInformation(**configdict)
