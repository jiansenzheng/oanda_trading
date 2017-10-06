# trading parameters for EUR_USD

IDXU= 220    #236

SHORT_WINDOW1= 90  #15
LONG_WINDOW1 = 180  #30
SHORT_WINDOW2= 90 # 45
LONG_WINDOW2 = 180 #90 
THRES1= 0.045  # 0.05   #0.065  TREND 
THRES2= 0.023  # 0.03  #0.01  TREND
THRES3 = 0.045 # 0.066    #0.15 REVERSION
THRES4=  0.01     #0.02 REVERSION
ADF_THRES = 0.60

PIP = 10000.0
SL1 = 15.0/PIP   #10
TP1 = 15.0/PIP   #10
SL2 = 10.0/PIP   #10
TP2 = 10.0/PIP   #10

MA_dict= {'short_window1':SHORT_WINDOW1,
        'long_window1':LONG_WINDOW1,
        'short_window2':SHORT_WINDOW2,
        'long_window2':LONG_WINDOW2}
threshold_dict = {'thres1':THRES1,
                  'thres2':THRES2,
                  'thres3':THRES3,
                  'thres4':THRES4,
                  'adf_thres':ADF_THRES,
                  'idxu':IDXU}

sltp_dict = {'sl1':SL1,
            'tp1': TP1,
            'sl2': SL2,
            'tp2': TP2}