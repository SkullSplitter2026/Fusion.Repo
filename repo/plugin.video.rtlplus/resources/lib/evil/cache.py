
from time import time
from functools import wraps

from .import settings ,signals ,gui ,router ,mem_cache
from .constants import CACHE_EXPIRY ,CACHE_CLEAN_INTERVAL ,ROUTE_CLEAR_CACHE
from .log import log
from .language import _

funcs =[]

def enabled ():
    return settings .getBool ('use_cache',True )

def key_for (f ,*args ,**kwargs ):
    func_name =f .__name__ if callable (f )else f
    if not enabled ()or func_name not in funcs :
        return None
    return mem_cache ._build_key (func_name ,*args ,**kwargs )

def cached (*args ,**kwargs ):
    def decorator (f ,expires =CACHE_EXPIRY ,key =None ):
        @wraps (f )
        def decorated_function (*args ,**kwargs ):
            _key =key or mem_cache ._build_key (f .__name__ ,*args ,**kwargs )
            if callable (_key ):
                _key =_key (*args ,**kwargs )
            if not kwargs .pop ('_skip_cache',False ):
                value =mem_cache .get (_key )
                if value is not None :
                    return value
            value =f (*args ,**kwargs )
            if value is not None :
                mem_cache .set (_key ,value ,expires )
            return value
        funcs .append (f .__name__ )
        return decorated_function
    return lambda f :decorator (f ,*args ,**kwargs )

def get (key ,default =None ):
    return mem_cache .get (key ,default )

def set (key ,value ,expires =CACHE_EXPIRY ):
    mem_cache .set (key ,value ,expires )

def delete (key ):
    return mem_cache .delete (key )

def empty ():
    mem_cache .empty ()

@router .route (ROUTE_CLEAR_CACHE )
def clear_cache (key ,**kwargs ):
    delete_count =delete (key )
    gui .notification (_ .PLUGIN_CACHE_REMOVED )
