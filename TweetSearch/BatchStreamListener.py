from tweepy import OAuthHandler
from tweepy import API
from tweepy import Stream
from secrets import *
from textblob import TextBlob
import os
import jsonpickle
import dataset
import pandas as pd
import numpy as np
from datafreeze import freeze
import argparse
from tweepy.streaming import StreamListener

print("Setting up twitter authentication...")
# Consumer key authentication
auth = OAuthHandler(consumer_key, consumer_secret)

# Access key authentication
auth.set_access_token(access_token, access_token_secret)

# Set up the API with the authentication handler
api = API(auth, wait_on_rate_limit=True)

print("Authentication done.")

from tweepy.streaming import StreamListener
import json
import time
import sys

class OriginalListener(StreamListener):
    '''This a batch extractor, it extraccts tweets in batches as defined by the batch size parameter'''
    def __init__(self, foldername, batchsize, verbose = False, api = None, fprefix = 'streamer', locationANDkey = False):
        # set up API
        self.api = api or API()
        self.counter = 0 # number of tweets?
        self.fprefix = fprefix
        self.output  = open('%s/%s_%s.json' % (foldername, self.fprefix, time.strftime('%Y%m%d-%H%M%S')), 'w')
        self.batchsize = batchsize
        self.verbose = verbose
        self.locationANDkey = locationANDkey


    def on_data(self, data):
        if  'in_reply_to_status' in data:
            '''If tweet is is in_reply to another tweet pass the on_status method, which stores the tweet'''
            self.on_status(data)
        elif 'delete' in data:
            '''If tweet was deleted do not return'''
            delete = json.loads(data)['delete']['status']
            if self.on_delete(delete['id'], delete['user_id']) is False:
                return False
        elif 'limit' in data:
            if self.on_limit(json.loads(data)['limit']['track']) is False:
                return False
        elif 'warning' in data:
            warning = json.loads(data)['warnings']
            print("WARNING: %s" % warning['message'])
            return


    def on_status(self, status):
        self.output.write(status)
        tweet = json.loads(status)
        if self.locationANDkey:
            '''Performs search within streaming tweets (not optimal)'''
            if not any(word in tweet["text"] for word in args.keyword):
                if self.verbose:
                    print("Found tweet in location but no matching keywords were found.")
                return 
        
        if self.verbose:
            print(tweet["created_at"], tweet["text"])
        self.counter += 1
        if self.counter >= self.batchsize: #tweet batch size
            print("+"+str(self.batchsize)+" tweets have been streamed and stored.")
            self.output.close()
            self.output  = open('%s/%s_%s.json' % (foldername, self.fprefix, time.strftime('%Y%m%d-%H%M%S')), 'w')
            self.counter = 0 # uncomment to keep streaming going
        return


    def on_delete(self, status_id, user_id):
        print("Delete notice")
        return


    def on_limit(self, track):
        print("WARNING: Limitation notice received, tweets missed: %d" % track)
        return


    def on_error(self, status_code):
        print('Encountered error with status code:', status_code)
        return 


    def on_timeout(self):
        print("Timeout, sleeping for 60 seconds...")
        time.sleep(60)
        return 
        
parser = argparse.ArgumentParser(description='Give some words to track on Twitter')
parser.add_argument("--keyword",'-k',type =str, 
                  help='1+ keyword(s) to track on twitter', nargs='+')
parser.add_argument("--location",'-l',type =str, 
                  help='City or region to track on twitter', nargs = '+')
parser.add_argument("--coordinates",'-cord',type =float, 
                  help='Custom region defined by polygon coordinates to track. You should give coordinates of the southwest corner first and then the coordinates or the northeast corner (format: longitude latitude (~ x y))', nargs='+')
parser.add_argument('--output','-o', type=str, action = 'store',
                  help = "Directory name to store streaming results(default: StreamDir)", default = "StreamDir")
parser.add_argument('--batch-size','-bs', type=int, help = 'Size of every bacth of tweets(default = 10000)', default = 10000)
parser.add_argument('--verbose','-v', dest='verbose', action='store_true')
parser.set_defaults(verbose=False)
args = parser.parse_args()

if not args.keyword and not args.location and not args.coordinates:
    raise Exception("No keyword, location or coordinates provided, please enter either of those arguments to start a search.")

RegionDictionary = []
with open("RegionCoords.json", 'r') as file:
    for line in file:
        RegionDictionary.append(json.loads(line))
RegionDictionary = pd.DataFrame(RegionDictionary)

args.location = [location.lower() for location in args.location] if args.location else None
print(args.location)
if args.location:
    print(True)
else:
    print(False)

if args.location or args.coordinates:
    if args.location and any(location in RegionDictionary["Region"].values for location in args.location):
        '''If the user has entered a location and the location is available do this'''
        # match input argument 
        regions_in_both = set(RegionDictionary["Region"]) & set(args.location)
        
        #warn of the unknown values
        if any(location not in RegionDictionary["Region"].values for location in args.location):
            print("Warning, location(s): "+
                  ', '.join(elem for elem in list(set(args.location).difference(set(RegionDictionary["Region"]))))+
                  "; are not known")
            
        # take coordinates of matching regions
        coords_from_location = list(
            RegionDictionary[RegionDictionary["Region"].values == list(regions_in_both)
            ].values
        )
        
        # remove cities so that it can be passed to locations argument
        coords_from_location = list(
            np.array(
                [coords[1:] for coords in coords_from_location]
            ).flatten()
        )
        
    elif args.coordinates:
        '''If the user has not entered a location or '''
        pass 
    else:
        raise Exception("Input location not available in RegionCoords.json, please enter a valid location or alternatively add the region to the json file with the help of the DumpingJSONs script or by inputting the coordinates manually with the --coordinates argument")
    

print(args)
print("Streaming results with tweets containing: "+(', '.join([str(elem) for elem in args.keyword]) if args.keyword else "NO KEYWORDS")+
      "; will be stored in the directory "+args.output+"/.\nVerbose output is "+("enabled" if args.verbose else "disabled")+
     ".\nLocation search has been "+("enabled." if args.location or args.coordinates else "disabled."))

foldername = args.output
if not os.path.exists(foldername):
    os.makedirs(foldername)

keywords_to_track = args.keyword
# Instantiate the SListener object 
listen = OriginalListener(api = api, foldername = args.output, batchsize = args.batch_size, verbose = args.verbose, locationANDkey = args.keyword and (args.location or args.coordinates))

# Instantiate the Stream object
stream = Stream(auth, listen)
print("Starting stream, press CTRL-C to stop.\n\n")
# Begin collecting data
if args.keyword and not args.location and not args.coordinates:
    stream.filter(track = keywords_to_track, is_async = True) 
elif args.location and not args.coordinates:
    stream.filter(locations=coords_from_location, is_async = True)
elif not args.location and args.coordinates:
    stream.filter(locations=args.coordinates, is_async = True)
elif args.keyword and (args.location or args.coordinates):
    print("WARNING: This search mode is not supported with the Twitter API, though a manual work around has been established. Performance is not as good")
    try:
        stream.filter(locations=coords_from_location, is_async = True) 
    except:
        stream.filter(locations=args.coordinates, is_async = True) 

# Streams do not terminate unless the connection is closed, blocking the thread. Tweepy offers a convenient is_async parameter on filter so the stream will run on a new thread.
