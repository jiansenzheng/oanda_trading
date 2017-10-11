#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 03 23:09:30 2017

@author: Jiansen
"""
import copy
import logging
import os
import json
from scipy import stats
import pandas as pd
import math
import numpy as np
import pywt
import time
import datetime
import statsmodels.tsa.stattools as ts

def get_indicator(instrument,s_ma,l_ma,gran,liq,short_slope,long_slope):
	utc_date=str(datetime.datetime.utcnow())
	time0=datetime.datetime.strptime(utc_date, '%Y-%m-%d %H:%M:%S.%f')
	date = time0.strftime("%Y-%m-%d")
	hms  = time0.strftime("%H:%M:%S")
	ms   =  time0.microsecond
	sec  =  3600*time0.hour+60*time0.minute+ time0.second
	sec_ms = sec*1000+ms
	post = {u'date':date, u'hms':hms, u'ms':ms, u'sec':sec, u'sec_ms':sec_ms,
			u'instrument':instrument, u'gran':gran, u'liq':liq, u's_ma':s_ma,u'l_ma':l_ma,
			u's_slope':short_slope,u'l_slope':long_slope}
	return post

def getDoc(data):
	lis=data['tick']
	ask,bid = lis['ask'],lis['bid']
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
		logging.warning("the series is too short!")
		return X

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

def getSlope(aa):
	'''
	return the slope ratio of a time series
	---args---
	aa: a (np.ndarray) object as a time series
	'''
	return stats.linregress(np.arange(0,len(aa),1),aa)[0]

def get_new_price_lis(price_lis,pairs_dict,window):
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