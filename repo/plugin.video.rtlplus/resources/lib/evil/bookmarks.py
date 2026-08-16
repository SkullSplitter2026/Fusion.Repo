import os
import json

from .constants import BOOKMARK_FILE
from .util import load_json ,save_json

path =os .path .dirname (BOOKMARK_FILE )
if not os .path .exists (path ):
    os .makedirs (path )

def add (path ,label =None ,thumb =None ,folder =1 ,playable =0 ,fanart =None ,poster =None ,series_title =None ):
    data =_load_favourites ()
    data =[x for x in data if x ['path']!=path ]
    entry ={'path':path ,'label':label ,'thumb':thumb ,'folder':folder ,'playable':playable }
    if fanart :entry ['fanart']=fanart
    if poster :entry ['poster']=poster
    if series_title :entry ['series_title']=series_title
    data .append (entry )
    _save_favourites (data )

def move (index ,shift ):
    data =_load_favourites ()

    bookmark =data .pop (index )
    if not bookmark :
        return

    data .insert (index +shift ,bookmark )
    _save_favourites (data )
    return data

def rename (index ,name ):
    data =_load_favourites ()
    data [index ]['label']=name
    _save_favourites (data )
    return data

def delete (index ):
    data =_load_favourites ()
    data .pop (index )
    _save_favourites (data )
    return data

def get ():
    return _load_favourites ()

def _load_favourites ():
    return load_json (BOOKMARK_FILE ,raise_error =False )or []

def _save_favourites (data ):
    save_json (BOOKMARK_FILE ,data ,pretty =True )