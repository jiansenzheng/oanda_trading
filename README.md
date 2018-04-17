# Automatic Live Trading with the Oanda API Based on Python Multithreading

Oanda\_trading is an open-sourced software written in Python to perform algorimic trading with Oanda API. We apply the multithreading framework to handle the market data streaming, trading signal calculation, and order sending. 

![alt text](https://github.com/jiansenzheng/oanda_trading/blob/master/trading_system_front-end.png)
## Getting Started
1. Obtain the access token and account ID from the official website of [OANDA](https://www.oanda.com/).
2. Install MongoDB(v3.2.4), start it as system service.
3. Install Python(2.7.13) , PyMongo(v3.2.2) and other necessary libraries.   
4.  After putting the python scripts in the same directory, modify the access token and account ID in *settings.py*, change the logging setting in *trading_log.py*.  
5. Start MongoDB as system service:

`sudo service mongod start`

6. Create the database and collections mentioned in the main script(*forex_trading_general_171005.py*) in MongoDB.
7. Open a terminal enter the same directory of these python scripts, and start to run the trading program as below,

`python forex_trading_general_171005.py`

8. Now you can check the trading signal logs in the log file, and implement your own trading strategy in the main script.
### Prerequisites

It is recommended that you run the script in a Ubuntu 14.04/16.04/17.04 LTS system where MognoDB is installed. 

You also need an installation of Python 2.7 from Anaconda. 

List of Python packages needed: 

* Pandas
* Numpy
* PyMongo
* PyWavelets 
* oandapy (Python wrapper for the OANDA REST API )
* python-requests

### Installing

No installation is required so far for this trading library.

---

## Deployment

Please read this blog (https://www.quantstart.com/articles/Forex-Trading-Diary-1-Automated-Forex-Trading-with-the-OANDA-API) on QuantStart.com before the deployment of this trading program on the clouds or your local servers

## Documentation
Please check out architecture\_of\_oanda\_trading.pdf for the multi-threading architecture of this trading system.

Gona make the Wiki page soon:)
## Authors

* **Jiansen Zheng** - [LinkedIn](https://www.linkedin.com/in/jiansen-zheng-b1a10a33/)

jiansenzheng@gmail.com

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Inspired by Michael Halls-Moore from quantstart.com

## Bitcoin Donation

* If you would like to support my project, please consider donating to this address: 35TkyWD4Vwp66hX8b8U8stABSDyW3pcCS1 
