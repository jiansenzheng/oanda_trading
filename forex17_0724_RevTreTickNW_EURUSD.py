#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 06 20:00:30 2016

@author: Jiansen
"""
import requests
import threading
import copy
import logging
import os
#import urllib3
import json
from scipy import stats
#from decimal import Decimal, getcontext, ROUND_HALF_DOWN

#from event00 import TickEvent,TickEvent2
#import time
import oandapy
import httplib
import pandas as pd
import math
import numpy as np
import pywt
import time
from settings import STREAM_DOMAIN, API_DOMAIN, ACCESS_TOKEN, ACCOUNT_ID
from param_EUR_USD import MA_dict, threshold_dict,sltp_dict
import Queue

#for writing data
import datetime
from bson.objectid import ObjectId
import pymongo as pm
from pymongo import MongoClient
import statsmodels.tsa.stattools as ts
#requests.adapters.DEFAULT_RETRIES = 5
from warningOps import warning
from seriesADF import getADF
corpid=  'wxf8ba6658b456540b'
secret='f78XFqKjNnNJF8Mpkb3BVh4BMpa-vbChBWMHu653KjFL0-mqT67lDQlt5YaEeD6w'
warn = warning(corpid,secret)
client = MongoClient('localhost',27017)
collection = client.test_database.tick_test 


def getDoc(data):
    lis=data['tick']
    ask=lis['ask']
    bid=lis['bid']
    instrument=lis['instrument']
    time0=datetime.datetime.strptime(lis['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
    date = time0.strftime("%Y-%m-%d")
    hms  = time0.strftime("%H:%M:%S")
    ms   =  time0.microsecond
    sec  =  3600*time0.hour+60*time0.minute+ time0.second
    sec_ms = sec*1000+ms
    post = {u'ask':ask, u'bid': bid,u'instrument': instrument, u'date':date, 
            u'hms':hms,u'ms':ms,u'sec':sec,u'sec_ms':sec_ms}
    return post

def denoise(X,wave0):
    wavelet=wave0
    if len(X)>=8:
        level0= 1
        if np.floor(np.log(len(X)))>7:
           level0= np.floor(np.log(len(X))/2.0) 
        thres = 2*np.sqrt(2*np.log(len(X))/len(X))*np.std(X)
        thres = 0.0
        WaveletCoeffs = pywt.wavedec(X, wavelet, level=level0)
        NewWaveletCoeffs = map (lambda x: pywt.threshold(x, thres, mode='hard'),WaveletCoeffs)
        newWave2 = pywt.waverec( NewWaveletCoeffs, wavelet)
        return newWave2
    else:
        logging.warning( "the series is too short")
        return X


#compute the liquidity index
def ohlcv_lis(lis):
    def get_ohlcv(candle, i):
        return map(candle[i].get,["openMid","highMid","lowMid","closeMid","volume"])    
    ohlcv1 = np.array([get_ohlcv(lis,0)])
    for i in range(1,len(lis)-1,1): # drop the last row
        ohlcv1 = np.concatenate((ohlcv1, np.array([get_ohlcv(lis,i)])),axis=0)
    return ohlcv1

def liq15min(lis):
    def vol_F(q1, q2, q3, q4):
        return (math.sqrt(math.log(q2/q3) - 2.0*(2.0*math.log(2.0) - 1.0)*math.log(q4/q1)))    
    liq = 0.0
    sigma = pd.Series()
    for i in range(0,len(lis),1):
        s1 = vol_F(lis[i,0],lis[i,1],lis[i,2],lis[i,3])
        sigma = np.append(sigma,s1)
    liq = math.sqrt(np.sum(lis[:,4])/100)/np.mean(sigma)
    liq = round(liq)
    return liq
    


#-------------------------#
class Event(object):
    pass
        
class TickEvent2(Event):
    def __init__(self, instrument, time, bid, ask):
        self.type = 'TICK'
        self.instrument = instrument
        self.time = time
        self.bid = bid
        self.ask = ask
        
class LiqEvent(Event):
    def __init__(self, instrument, time, liq):
        self.type = 'LIQ'
        self.instrument = instrument
        self.time = time
        self.liq = liq

class OrderEvent(Event):
    def __init__(self, instrument, units, order_type, side, stopLoss, takeProfit,stra):
        self.type = 'ORDER'
        self.instrument = instrument
        self.units = units
        self.order_type = order_type
        self.side = side
        self.stopLoss = stopLoss,
        self.takeProfit = takeProfit
        self.stra = stra
                
class CloseEvent(Event):
    def __init__(self, instrument,num):
        self.type = 'CLOSE'
        self.instrument = instrument
        self.num = num
#--------------------------Liq------------------------------------------#
class LiqForex(object):
    def __init__(
        self, domain, access_token,
        account_id, instruments,ct, gran, dd, events_queue
    ):
        self.domain = domain
        self.access_token = access_token
        self.account_id = account_id
        self.instruments = instruments
        self.ct = ct
        self.gran=gran
        self.dd= dd
        self.events_queue = events_queue
        
    def getLiq(self):
        try:
            requests.packages.urllib3.disable_warnings()
            s = requests.Session()
            #s.keep_alive = False
            url = "https://" + self.domain + "/v1/candles"
            headers = {'Authorization' : 'Bearer ' + self.access_token}
            params = {'instrument':self.instruments, 'accountId' : self.account_id,
                      'count':self.ct,'candleFormat':'midpoint','granularity':self.gran}
            req = requests.Request('GET', url, headers=headers, params=params)     
            pre = req.prepare()
            logging.info( pre)
            resp = s.send(pre, stream=False, verify=False)
            try:            
                msg=json.loads(resp.text)
            except Exception as e:
                logging.warning( "Caught exception when converting message into json\n" + str(e))
                return   
            if msg.has_key("candles"):    
                time=msg.get("candles")[-1]["time"]
                lis = ohlcv_lis(msg.get("candles"))
                liqS = pd.Series()
                for i in range(0, len(lis)- (self.dd+1) ,1):
                    s2 = liq15min(lis[i:i+self.dd])
                    liqS = np.append(liqS,s2)
                liq=liqS[-1] 
                logging.info( "liq=".format(liq))
                tev = LiqEvent(self.instruments,time,liq)
                self.events_queue.put(tev,False)
        except Exception as e:
            s.close()
            content0 = "Caught exception when connecting to history\n" + str(e)
            logging.warning(content0)
            #warn.tradingWarning(content0) 
    def activeLiq(self,period):
        while True:
            self.getLiq()    
            time.sleep(period)
#--------------------------------------------------------------------#
class StreamingForexPrices(object):
    def __init__(
        self, domain, access_token,
        account_id, instruments,ct, gran, dd, events_queue
    ):
        self.domain = domain
        self.access_token = access_token
        self.account_id = account_id
        self.instruments = instruments
        self.ct = ct
        self.gran=gran
        self.dd= dd
        self.events_queue = events_queue

    def connect_to_stream(self):
        try:
            requests.packages.urllib3.disable_warnings()
            s = requests.Session()  # socket
            url = "https://" + self.domain + "/v1/prices"
            headers = {'Authorization' : 'Bearer ' + self.access_token}
            params = {'instruments' : self.instruments, 'accountId' : self.account_id}
            time.sleep(0.8) # sleep some seconds
            req = requests.Request('GET', url, headers=headers, params=params)
            pre = req.prepare()
            resp = s.send(pre, stream=True, verify=False)
            return resp
        except Exception as e:
            #global s
            s.close()
            content0 = "Caught exception when connecting to stream\n" + str(e)
            logging.warning(content0)
            #warn.tradingWarning(content0)

    def stream_to_queue_old(self,collection):
        response = self.connect_to_stream()
        if response.status_code != 200:
            return
        for line in response.iter_lines(1):
            if line:
                try:
                    msg = json.loads(line)
                except Exception as e:
                    content0 = "Caught exception when converting message into json\n" + str(e)
                    logging.warning(content0)
                    return
                if msg.has_key("instrument") or msg.has_key("tick"):
                    logging.info(msg)
                    instrument = msg["tick"]["instrument"]
                    time = msg["tick"]["time"]
                    bid = msg["tick"]["bid"]
                    ask = msg["tick"]["ask"]
                    tev = TickEvent2(instrument, time, bid, ask)
                    self.events_queue.put(tev,False)
                    post= getDoc(msg)
                    collection.insert_one(post)
        
#--------------
#------
 # new strategy           
class LiqMAStrategy(object):
    """
    """
    def __init__(
        self, access_token, account_id, pairs, units, events, stopLoss1, takeProfit1,stopLoss2, takeProfit2,
        short_window1, long_window1,short_window2, long_window2, idxU, lam, thres1, thres2,thres3, thres4, adf_thres
    ):
        self.access_token = access_token
        self.account_id = account_id

        self.pairs = pairs
        self.units = units
        self.stopLoss1 = stopLoss1
        self.takeProfit1 = takeProfit1
        self.stopLoss2 = stopLoss2
        self.takeProfit2 = takeProfit2
        self.pairs_dict = self.create_pairs_dict()
        self.events = events
        self.short_window1 = short_window1
        self.long_window1 = long_window1
        self.short_window2 = short_window2
        self.long_window2 = long_window2
        self.idxU = idxU
        self.lam = lam
        self.priceLis1 = pd.Series()    #for trends
        self.priceLis2 = pd.Series()    #for reversion
        self.thres1 = thres1
        self.thres2 = thres2
        self.thres3 = thres3
        self.thres4 = thres4
        self.adf_thres = adf_thres


    def create_pairs_dict(self):
        attr_dict = {
            "ticks": 0,
            "tick0": 0,
            "priceLS":0.0,
            "invested": False,
            "short_sma": None,
            "long_sma": None,
            "longShort": None,
            "short_slope":None,
            "long_slope":None,  # False denotes sell, while True denotes buy
            "check": False,
            "orlis":[0,0,0,0],
            "stra": 0,
            "fixed": False
        }
        #pairs_dict = {}
        pairs_dict = copy.deepcopy(attr_dict)
        return pairs_dict

    def check_order(self,check):
        if check== True:
            oanda0 = oandapy.API(environment="practice", access_token=self.access_token)
            responseTrades = oanda0.get_trades(self.account_id,instrument=self.pairs)
            if responseTrades.get("trades")==[]:
                pd = self.pairs_dict
                pd["orlis"].pop(0)
                logging.info(" orlis: "+str(pd["orlis"])) 
                pd["orlis"].append(0)
                logging.info(" orlis: "+str(pd["orlis"])) 
                if pd["orlis"][0:4]==[1,1,0,0]:   
                    logging.warning( "Stop Loss Order Executed!")
                    #warn.tradingWarning(" Stop Loss Order Executed!")
                    pd["invested"]= False
                    pd["fixed"] = False  #position closed, the stra type is free
                    pd["check"] = False
                else:
                    pass
            else:
                pd = self.pairs_dict
                #pd["orlis"][0] = copy.copy(pd["orlis"][1])
                pd["orlis"].pop(0)
                pd["orlis"].append(1)
                logging.info("not empty- orlis: "+str(pd["orlis"])) 
                pd["invested"]= True
                pd["fixed"] = True  #position closed, the stra type is free
                pd["check"] = True              
        else:
            pass

    def getSlope(self,aa):
        '''
        return the slope ratio of a time series
        ---args---
        aa: a (np.ndarray) object as a time series
        '''
        return stats.linregress(np.arange(0,len(aa),1),aa)[0]

    def get_new_price_lis(self,price_lis,pairs_dict,window):
        '''
        change the attributes in pairs_dict and return it
        Arguments:
            pairs_dict {[type]} -- [description]
             {[type]} -- [description]
        '''
        newPriceLis =  denoise(price_lis,'db4')
        pairs_dict["short_sma"] = np.mean(newPriceLis[-window:])
        pairs_dict["long_sma"] =  np.mean(newPriceLis) 
        return newPriceLis 

    def compute_slope(self,price_lis,window_length,k):
        '''[summary]
        compute the slope ratio for a short time series
        Arguments:
            price_lis {np.ndarray} -- the filtered time series to compute the slope ratio
            for both SMA and LMA
            default: newPriceLis
            window_length {[type]} -- a parameter for the SMA
            k: an parameter for performing average, default->0.5
            default: self.short_window2
        Returns:
            [float] -- [the slope ratio]
        '''
        amp = lambda lis: (lis-lis[0])*10000.0
        pShort =   amp(price_lis[-window_length:])
        pLong =  amp(price_lis)
        #compute the slope ratio
        aveSlope = k*self.getSlope(pShort)+ (1-k)*self.getSlope(pLong)   
        return aveSlope

    def set_invested_check_fixed(self,pair_dict,invested_bool,check_bool,fixed_bool):
        pair_dict["invested"] = invested_bool
        pair_dict["check"] = check_bool
        pair_dict["fixed"] = fixed_bool
        time.sleep(0.0)                  

    def calculate_signals(self, event):
        #if True:        
        global liqIndex
        global newPriceLis
        if event.type == 'TICK':
            price = (event.bid+event.ask)/2.000
            self.priceLis1 = np.append(self.priceLis1,price)
            self.priceLis2 = np.append(self.priceLis2,price)
            if len(self.priceLis1)>max([self.long_window1,self.long_window2]):
                self.priceLis1=self.priceLis1[-self.long_window1:]
                self.priceLis2=self.priceLis2[-self.long_window2:]
            else:
                pass
            #liqIndex= event.liq
            logging.info("liqIndex= "+str(liqIndex)+"\n")
            logging.info("price= "+str(price))
            pd = self.pairs_dict
            logging.info("check"+str(pd["check"]))
            self.check_order(pd["check"])   #check whether the SLTP order is triggered..
            # Only start the strategy when we have created an accurate short window
            logging.info("INVESTED= "+str(pd["invested"]))
            if not pd["invested"]:
                #global price0
                if pd["ticks"]>max([self.long_window1, self.long_window2])+1 and liqIndex > self.idxU:
                    if not pd["fixed"]:
                        critAdf = getADF(collection).priceADF(200,1)
                        if critAdf > self.adf_thres:
                            pd["stra"] = "reversion"
                            newPriceLis = self.get_new_price_lis(self.priceLis2, pd, self.short_window2)
                            aveSlope = self.compute_slope(newPriceLis,self.short_window2, 0.5)
                            logging.info( "REVERSION+aveSlope="+str(aveSlope))
                        else:
                            pd["stra"] = "trends"
                            newPriceLis = self.get_new_price_lis(self.priceLis1, pd, self.short_window1)
                            aveSlope = self.compute_slope(newPriceLis,self.short_window1, 0.5)
                            logging.info("TRENDS+aveSlope="+str(aveSlope))
                    else:
                        raise ValueError("pd[fixed] should be False!")

                    price0, price1 = event.bid, event.ask
                    if pd["stra"] =="trends":
                        if pd["short_sma"] > pd["long_sma"] and aveSlope> self.thres1:
                            side = "buy"
                            logging.info("price02={0}".format(price0))
                            self.set_invested_check_fixed(pd,True,True,True)
                            sl_b, tp_b= round(price0 - self.stopLoss1,5),round(price1 + self.takeProfit1,5)
                            order = OrderEvent(self.pairs, self.units, "market", side, sl_b, tp_b,"Trends")
                            self.events.put(order)
                            pd["longShort"] = True
                            pd["tick0"]= pd["ticks"]
                            pd["priceLS"]= price0
                        elif pd["short_sma"] < pd["long_sma"] and aveSlope< -self.thres1:
                            side = "sell"
                            logging.info("price01={0}".format(price1))
                            self.set_invested_check_fixed(pd,True,True,True)
                            sl_s,tp_s = round(price1 + self.stopLoss1,5),round(price0 - self.takeProfit1,5)
                            order = OrderEvent(self.pairs, self.units, "market", side, sl_s, tp_s,"Trends")
                            self.events.put(order)
                            pd["longShort"] = False
                            pd["tick0"]= pd["ticks"]
                            pd["priceLS"]= price1
                        else:
                            pd["fixed"] = False

                    elif pd["stra"] =="reversion":
                        if pd["short_sma"] > pd["long_sma"] and aveSlope> self.thres3:
                            side = "sell"
                            logging.info("price02={0}".format(price1))
                            self.set_invested_check_fixed(pd,True,True,True)
                            sl_s,tp_s = round(price1+self.stopLoss2,5),round(price0-self.takeProfit2,5)
                            order = OrderEvent(self.pairs, self.units, "market", side, sl_s, tp_s,"reversion")
                            self.events.put(order)
                            pd["longShort"] = False
                            pd["tick0"]= pd["ticks"]
                            pd["priceLS"]= price0
                        elif pd["short_sma"] < pd["long_sma"] and aveSlope< -self.thres3:
                            side = "buy"
                            logging.info("price01={0}".format(price0))
                            self.set_invested_check_fixed(pd,True,True,True)
                            sl_b, tp_b = round(price0-self.stopLoss2,5),round(price1+self.takeProfit2,5)
                            order = OrderEvent(self.pairs, self.units, "market", side, sl_b, tp_b,"reversion")
                            self.events.put(order)
                            pd["longShort"] = True
                            pd["tick0"]= pd["ticks"]
                            pd["priceLS"]= price1
                        else:
                            pd["fixed"] = False
                    else:
                        pass
                else:
                    pass
            elif pd["invested"]:
                sign= 1 if pd["longShort"] == True else -1

                if pd["stra"] =="trends":
                    logging.info("Trends position!")                   
                    newPriceLis = self.get_new_price_lis(self.priceLis1, pd, self.short_window1)
                    basePrice=pd["priceLS"]+sign*self.lam*np.std(self.priceLis1)*np.sqrt(pd["ticks"]-pd["tick0"])
                    logging.info( "basePrice="+str(basePrice))
                    logging.info( "short_sma"+str(pd["short_sma"]))
                    logging.info( "long_sma"+str(pd["long_sma"]))
                    aveSlope = self.compute_slope(newPriceLis,self.short_window1, 0.5)
                    logging.info( "aveSlope="+str(aveSlope))
                    if  not pd["longShort"]  and aveSlope > -self.thres2:
                        #side = "sell"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        close_order = CloseEvent(self.pairs,0)
                        self.events.put(close_order)
                    elif pd["longShort"] and aveSlope < self.thres2:
                        #side = "buy"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        close_order = CloseEvent(self.pairs,0)
                        self.events.put(close_order)
                    else: #not closing positions, just keep the pd["fixed"] as True.
                        pd["fixed"] = True  #should we add pd["invested"]

                elif pd["stra"] =="reversion":
                    logging.info( "Reversion position!")                   
                    newPriceLis = self.get_new_price_lis(self.priceLis2, pd, self.short_window2)
                    basePrice=pd["priceLS"]+sign*self.lam*np.std(self.priceLis2)*np.sqrt(pd["ticks"]-pd["tick0"])
                    logging.info( "basePrice="+str(basePrice))
                    logging.info( "short_sma"+str(pd["short_sma"]))
                    logging.info( "long_sma"+str(pd["long_sma"]))
                    aveSlope = self.compute_slope(newPriceLis,self.short_window2, 0.5)
                    logging.info( "aveSlope="+str(aveSlope))
                    if pd["short_sma"] < pd["long_sma"]-0.00006  and not pd["longShort"]:
                        #side = "sell"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        close_order = CloseEvent(self.pairs,0)
                        self.events.put(close_order)
                    elif pd["short_sma"] > pd["long_sma"]+0.00006 and pd["longShort"]:
                        #side = "buy"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        close_order = CloseEvent(self.pairs,0)
                        self.events.put(close_order)
                    else:
                        pd["fixed"] = True  #should we add pd["invested"]
                else:
                    pass

            pd["ticks"] += 1
            logging.info("current Tick "+str(pd["ticks"])+"\n"+str(time.ctime()))

#--------------------------------------------------------------------#
class Execution(object):
    def __init__(self, domain, access_token, account_id):
        self.domain = domain
        self.access_token = access_token
        self.account_id = account_id
        self.conn = self.obtain_connection()

    def obtain_connection(self):
        return httplib.HTTPSConnection(self.domain)

    def execute_order(self, event):
        oanda0 = oandapy.API(environment="practice", access_token=self.access_token)
        try:
            responseX = oanda0.create_order(self.account_id,
            instrument=event.instrument,
            units= event.units,
            side= event.side,
            type= event.order_type,
            stopLoss =   event.stopLoss,
            takeProfit = event.takeProfit
            )           
        except Exception as e:
            content0 = "Caught OnadaError when sending the orders\n" + str(e)
            logging.warning(content0)
            return             
        logging.info( "Execute Order ! \n {0}".format(responseX))
        content0 = str(event.stra)+"Execute Order ! "+" "+str(event.side)+" "+ str(event.units)+" units of "+str(event.instrument)
        #warn.tradingWarning(content0)
        logging.info(content0)
        
    def close_order(self, event):
        oanda0 = oandapy.API(environment="practice", access_token=self.access_token)
        response1= oanda0.get_trades(self.account_id,instrument=event.instrument)
        order_lis= response1["trades"]
        if order_lis !=[]:
            for order in order_lis:  #close all trades
                responseX = oanda0.close_trade(self.account_id,trade_id= order['id'])
                logging.info( "Close Order ! \n {0}".format(responseX))
                content0  = "Close Order !" + "profit: "+str(responseX['profit'])+" CLOSE "+str(responseX['instrument'])
                content0  = content0 + " "+str(responseX['side'])+" at "+ str(responseX['price'])
                #warn.tradingWarning(content0)
        else:
            logging.warning("No trade to be closed! :{0}".format(time.ctime()))

#--------------------------------------------------------------------#
def trade(events, strategy,execution,heartbeat):
    """
    """
    global liqIndex
    while True: 
        try:
            event = events.get(False)
        except Queue.Empty:
            pass
        else:
            if event is not None:
                if event.type =='LIQ':
                    liqIndex= event.liq
                    #print "current index ="+str(liqIndex)
                elif event.type == 'TICK':
                    strategy.calculate_signals(event)
                    logging.info( "Tick!")
                elif event.type == 'ORDER':
                    logging.info( "Executing order!")
                    execution.execute_order(event)
                elif event.type == "CLOSE":
                    logging.info( "Close trading!")
                    execution.close_order(event)
        time.sleep(heartbeat)
#--------------------------------------------------------------------#        
if __name__ == "__main__":
    pairs = "EUR_USD"
    logPath = '/home/zheng/data/trading/EUR_USD/'
    logName = 'eur_usd.log'
    logging.basicConfig(filename= os.path.join(logPath,logName),
                    format='%(levelname)s:%(message)s',level=logging.DEBUG)    
    global liqIndex
    liqIndex=0
    ct = 20
    gran ='M15'
    time_dict = {
    "S5": 5,
    "S10": 10,
    "S15": 15,
    "S30": 30,
    "M1": 60,
    "M2": 120 }
    dd = 11
    lam= 0.1     #0.5 basePrice tuning
    units = 100    #100
    #----------Parameters----------------
    short_window1= MA_dict['short_window1']  
    long_window1 = MA_dict['long_window1']
    short_window2= MA_dict['short_window2']
    long_window2 = MA_dict['long_window2']

    idxu = threshold_dict['idxu']    
    thres1= threshold_dict['thres1'] 
    thres2= threshold_dict['thres2'] 
    thres3 = threshold_dict['thres3'] 
    thres4= threshold_dict['thres4'] 
    adf_thres =  threshold_dict['adf_thres']

    sl1 = sltp_dict['sl1']   #10
    tp1 = sltp_dict['tp1']   #10
    sl2 = sltp_dict['sl2']   #10
    tp2 = sltp_dict['tp2']   #10
    #--------------------------------------
    #pairs = "EUR_USD"
    #pip = 10000.0
    heartbeat= 0.2 
    period= 600    
    print 'initial'
    print('MA:\n sw1 {0} lw1 {1} sw2 {2} lw2 {3}'.format(short_window1, long_window1, short_window2, long_window2))
    print('parameters:\n thres1 {0} thres2 {1} thres3 {2} thres4 {3}'.format(thres1,thres2,thres3,thres4))
    print('sltp_parameters:\n {0} {1} {2} {3}'.format(sl1,tp1,sl2,tp2))    
    events = Queue.Queue()
    # initial the threads
    prices = StreamingForexPrices(STREAM_DOMAIN, ACCESS_TOKEN, ACCOUNT_ID, pairs, ct, gran, dd, events)
    liquidity = LiqForex(API_DOMAIN, ACCESS_TOKEN, ACCOUNT_ID, pairs, ct, gran, dd, events)
    execution = Execution(API_DOMAIN, ACCESS_TOKEN, ACCOUNT_ID)
    #strategy = MovingAverageCrossStrategy(pairs, units, events, sl, tp, short_window,long_window)
    strategy = LiqMAStrategy(ACCESS_TOKEN, ACCOUNT_ID, pairs, units, events, sl1, tp1, sl2, tp2, short_window1,long_window1,
        short_window2,long_window2,idxu,lam,thres1,thres2,thres3,thres4,adf_thres)
    # construct the thread
    price_thread = threading.Thread(target=prices.stream_to_queue_old, args=[collection])
    liq_thread = threading.Thread(target= liquidity.activeLiq, args=[period])
    trade_thread = threading.Thread(target=trade, args=(events, strategy,execution,heartbeat))
    print "Full?:",events.full()
    trade_thread.start() 
    price_thread.start()
    liq_thread.start()


