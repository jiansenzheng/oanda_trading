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

from trading_events import Event,TickEvent2,LiqEvent,OrderEvent,CloseEvent
from trading_global_functions import *
from trading_log import log_dict

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

#------the only line we need to change is about the instruments----#
pairs = "EUR_USD"
#-----------------------------------------------------------------------#


client = MongoClient('localhost',27017)
db = client.test_database

#---------------Initialize the parameters and database connections-------#
if pairs == "EUR_USD":
    try:
        from param_EUR_USD import MA_dict, threshold_dict,sltp_dict
    except ImportError:
        raise ValueError("cannot find parameters for {0}!".format(pairs))
    collection = db.tick_test 
    index_collect = db.index_EUR_USD
elif pairs == "USD_CNH":
    try:
        from param_USD_CNH import MA_dict, threshold_dict,sltp_dict
    except ImportError:
        raise ValueError("cannot find parameters for {0}!".format(pairs))
    collection = db.tick_USD_CNH 
    index_collect = db.index_USD_CNH

elif pairs == "AUD_USD":
    try:
        from param_AUD_USD import MA_dict, threshold_dict,sltp_dict
    except ImportError:
        raise ValueError("cannot find parameters for {0}!".format(pairs))
    collection = db.tick_AUD_USD 
    index_collect = db.index_AUD_USD

else:
    raise ValueError('Invalid <pairs>, CANNOT FIND THE INSTRUMENTS!')
#-----------------------------------------------------------------------#


#--------------------------Liquidity Index------------------------------#
#-----------------------------------------------------------------------#
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
                time0=msg.get("candles")[-1]["time"]
                lis = ohlcv_lis(msg.get("candles"))
                liqS = pd.Series()
                for i in range(0, len(lis)- (self.dd+1) ,1):
                    s2 = liq15min(lis[i:i+self.dd])
                    liqS = np.append(liqS,s2)
                liq=liqS[-1] 
                logging.info( "liq=".format(liq))
                tev = LiqEvent(self.instruments,time0,liq)
                self.events_queue.put(tev,False)
                post_metric = get_indicator(self.instruments,None,None,self.gran,liq,None,None) 
                index_collect.insert_one(post_metric)                
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
        try:
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
                        time0 = msg["tick"]["time"]
                        bid = msg["tick"]["bid"]
                        ask = msg["tick"]["ask"]
                        tev = TickEvent2(instrument, time0, bid, ask)
                        self.events_queue.put(tev,False)
                        post= getDoc(msg)
                        collection.insert_one(post)
        except Exception as e:
            logging.warning('Caught ChunkedEncodingError in  stream_to_queue_old()!'+str(time.ctime()))
            return
        
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
        #---intermediates---#
        self.SL_TP = {"trends":[self.stopLoss1,self.takeProfit1],
                    "reversion":[self.stopLoss2,self.takeProfit2]}
        self.s_l_window = {"trends":[self.short_window1,self.long_window1],
                    "reversion":[self.short_window2,self.long_window2]}
        self.thres_tre_rev = {"trends":[self.thres1, self.thres2],
                            "reversion":[self.thres3,self.thres4]}                     

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
            try:
                responseTrades = oanda0.get_trades(self.account_id,instrument=self.pairs)
            except Exception as e:
                logging.warning('Caught exception in get_trades() of check_order()!\n'+str(time.ctime()))
                return            
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
        aveSlope = k*getSlope(pShort)+ (1-k)*getSlope(pLong)   
        return aveSlope

    def set_invested_check_fixed(self,pair_dict,invested_bool,check_bool,fixed_bool):
        pair_dict["invested"] = invested_bool
        pair_dict["check"] = check_bool
        pair_dict["fixed"] = fixed_bool
        time.sleep(0.0)

    def get_sl_tp(self,TreRev):
        return self.SL_TP[TreRev]

    def insert_metric(self,collection,pair_dict):
        '''
        default collection: index_USD_CNH
        '''
        short_window,long_window = self.s_l_window[pair_dict["stra"]]
        post_metric = get_indicator(self.pairs,short_window,long_window,
                                    None,None,pair_dict["short_slope"],pair_dict["long_slope"]) 
        collection.insert_one(post_metric)
#----------------#
    def buy_send_order(self,pd,side,price0,price1,TreRev):
        logging.info("price02={0}".format(price0))
        self.set_invested_check_fixed(pd,True,True,True)
        fixSL, fixeTP = self.get_sl_tp(TreRev)
        sl_b, tp_b= round(price0 - fixSL,5),round(price1 + fixeTP,5)
        order = OrderEvent(self.pairs, self.units, "market", side, sl_b, tp_b,"Trends")
        self.events.put(order)
        pd["longShort"] = True
        pd["tick0"]= pd["ticks"]
        pd["priceLS"]= price0   
        
    def sell_send_order(self,pd,side,price0,price1,TreRev):
        logging.info("price01={0}".format(price1))
        self.set_invested_check_fixed(pd,True,True,True)
        fixSL, fixeTP = self.get_sl_tp(TreRev)
        sl_s,tp_s = round(price1 + fixSL,5),round(price0 - fixeTP,5)
        order = OrderEvent(self.pairs, self.units, "market", side, sl_s, tp_s,"Trends")
        self.events.put(order)
        pd["longShort"] = False
        pd["tick0"]= pd["ticks"]
        pd["priceLS"]= price1                               

    def logging_invested(self,priceLis,pd,sign):
        TreRev = pd["stra"]
        logging.info(TreRev+" position!")
        #??? TODO  23:38 Oct 5, 2017
        short_window = self.s_l_window[TreRev][0]          
        newPriceLis = get_new_price_lis(priceLis, pd, short_window)
        basePrice=pd["priceLS"]+sign*self.lam*np.std(priceLis)*np.sqrt(pd["ticks"]-pd["tick0"])
        logging.info( "basePrice="+str(basePrice))
        logging.info( "short_sma"+str(pd["short_sma"]))
        logging.info( "long_sma"+str(pd["long_sma"]))
        aveSlope = self.compute_slope(newPriceLis,short_window, 0.5)
        logging.info( "aveSlope="+str(aveSlope)) 
        return aveSlope

    def put_close_order(self,pairs,num):
        '''
        pairs,num = self.pairs,0
        '''
        order_closed = CloseEvent(pairs,num)
        self.events.put(order_closed)          
#--------------------------------------#
    def open_trends_buy(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][0]
        return (pd["short_sma"] > pd["long_sma"] and aveSlope > thres)

    def open_trends_sell(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][0]
        return (pd["short_sma"] < pd["long_sma"] and aveSlope < -thres)

    def open_reversion_buy(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][0]
        return (pd["short_sma"] < pd["long_sma"] and aveSlope< -thres)

    def open_reversion_sell(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][0]
        return (pd["short_sma"] > pd["long_sma"] and aveSlope> thres)
#-----------------------------------------------#
    def close_trends_buy(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][1]
        return (pd["longShort"] and aveSlope < thres)

    def close_trends_sell(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][1]
        return (not pd["longShort"]  and aveSlope > -thres)

    def close_reversion_buy(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][1]
        return (pd["short_sma"] > pd["long_sma"]*(1+thres/100.0)  and pd["longShort"])

    def close_reversion_sell(self,pd,aveSlope):
        thres = self.thres_tre_rev[pd["stra"]][1]
        return (pd["short_sma"] < pd["long_sma"]*(1-thres/100.0)  and not pd["longShort"])
#--------------------------------------#
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
                            newPriceLis = get_new_price_lis(self.priceLis2, pd, self.short_window2)
                            aveSlope = self.compute_slope(newPriceLis,self.short_window2, 0.5)
                            logging.info( "REVERSION+aveSlope="+str(aveSlope))
                            self.insert_metric(index_collect,pd)
                        else:
                            pd["stra"] = "trends"
                            newPriceLis = get_new_price_lis(self.priceLis1, pd, self.short_window1)
                            aveSlope = self.compute_slope(newPriceLis,self.short_window1, 0.5)
                            logging.info("TRENDS+aveSlope="+str(aveSlope))
                            self.insert_metric(index_collect,pd)
                    else:
                        raise ValueError("pd[fixed] should be False!")

                    price0, price1 = event.bid, event.ask
                    if pd["stra"] =="trends":
                        if self.open_trends_buy(pd,aveSlope):
                            side = "buy"
                            self.buy_send_order(pd,side,price0,price1,pd["stra"])
                        elif self.open_trends_sell(pd,aveSlope):
                            side = "sell"
                            self.sell_send_order(pd,side,price0,price1,pd["stra"])
                        else:
                            pd["fixed"] = False
                    elif pd["stra"] =="reversion":
                        if self.open_reversion_sell(pd,aveSlope):
                            side = "sell"
                            self.sell_send_order(pd,side,price0,price1,pd["stra"])
                        elif self.open_reversion_buy(pd,aveSlope):
                            side = "buy"
                            self.buy_send_order(pd,side,price0,price1,pd["stra"])
                        else:
                            pd["fixed"] = False
                    else:
                        pass
                else:
                    pass
            elif pd["invested"]:
                sign= 1 if pd["longShort"] == True else -1

                if pd["stra"] =="trends":
                    aveSlope = self.logging_invested(self.priceLis1,pd,sign)
                    self.insert_metric(index_collect,pd)
                    if  self.close_trends_sell(pd,aveSlope):
                        #side = "sell"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        self.put_close_order(self.pairs,0)

                    elif self.close_trends_buy(pd,aveSlope):
                        #side = "buy"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        self.put_close_order(self.pairs,0)

                    else: #not closing positions, just keep the pd["fixed"] as True.
                        pd["fixed"] = True  #should we add pd["invested"]

                elif pd["stra"] =="reversion":
                    aveSlope=self.logging_invested(self.priceLis2,pd,sign)
                    self.insert_metric(index_collect,pd)
                    if self.close_reversion_sell(pd,aveSlope):
                        #side = "sell"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        self.put_close_order(self.pairs,0)

                    elif self.close_reversion_buy(pd,aveSlope):
                        #side = "buy"
                        self.set_invested_check_fixed(pd,False,False,False)
                        #warn.tradingWarning(" check->False Executed!")
                        self.put_close_order(self.pairs,0)

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
    
    logPath,logName = log_dict[pairs]["path"],log_dict[pairs]["name"]
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


