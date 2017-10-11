# Automatic Live Trading with the Oanda API Based on Python

Oanda\_trading is an open-sourced software written in Python to perform algorimic trading with Oanda API. We apply the multithreading framework to handle the market data streaming, trading signal calculation, and order sending. 

## Getting Started
Put the files in the same directory, and once MongoDB(v3.2.4) is installed, you can run the trading program as below:

python forex\_trading\_general\_171005.py


### Prerequisites

It is recommended that you run the script in a Ubuntu 16.04 LTS system where MognoDB is installed. 

You also need an installation of Python 2.7 from Anaconda. 

List of Python libraries needed: 

* Pandas
* Numpy
* PyMongo
* PyWavelets 
* oandapy (Python wrapper for the OANDA REST API )
* python-requests

### Installing

No installation required so far.

## Deployment

Please read this blog (https://www.quantstart.com/articles/Forex-Trading-Diary-1-Automated-Forex-Trading-with-the-OANDA-API) on QuantStart.com before the deployment of this trading program on the clouds or your local servers


## Authors

* **Jiansen Zheng** - [LinkedIn](https://www.linkedin.com/in/jiansen-zheng-b1a10a33/)


## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* Inspired by Michael Halls-Moore from quantstart.com

