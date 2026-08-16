
import os
from .import signals
from .log import log
from .constants import DB_PATH

tables =[]

def check_tables ():
    pass

@signals .on (signals .AFTER_RESET )
def delete ():
    try :
        if os .path .exists (DB_PATH ):
            os .remove (DB_PATH )
    except Exception as e :
        log .debug ('db delete error: {}'.format (e ))

@signals .on (signals .ON_CLOSE )
def close ():
    pass

@signals .on (signals .BEFORE_DISPATCH )
def connect ():
    pass
