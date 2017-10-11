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
		self.num = num  #keep it for the moment.