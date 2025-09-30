# **🇬🇧 English Readme (Temporary SMS Receiver Monitor)**
<div align="center">

<img src="https://i.meee.com.tw/ikqBwaY.jpg" alt="Project Banner" style="border-radius: 10px; margin-top: 10px; margin-bottom: 10px;width: 200px; height: 200px;">

</div>

<p align="center">  
<strong>English</strong> •  
<a href="./README.md"><strong>繁體中文 (Traditional Chinese)</strong></a>  
</p>

This project is a Python application designed to scrape a specific website for temporary SMS receiver numbers. It uses **Selenium** to bypass anti-bot protections and a **ThreadPoolExecutor** for concurrent checking of multiple number pages to identify "active numbers" that have received a new SMS within the last hour.

![Demo GIF](demo.png)

It offers two execution modes:

1. **Local Execution (main.py)**: For running on your local machine, with the option to use ngrok for a public URL.  
2. **Colab Execution (public.py)**: Tailored for Google Colaboratory, enabling cloud execution and quick public URL tunneling via ngrok.

## **🚀 Project Setup**

### **1\. Prerequisites**

* Python 3.10 or newer.  
* uv (recommended package manager) or pip.  
* Google Chrome browser (for local execution).  
* [ngrok Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) (optional but recommended for public access).

### **2\. Install Dependencies**

The project uses pyproject.toml. Install dependencies using uv or pip:

`uv sync`  
\# OR  
`pip install beautifulsoup4 flask pyngrok requests selenium tomli waitress webdriver-manager`

### **3\. Configuration (config.toml)**

Edit the config.toml file to suit your needs:

| Setting | Description |
| :---- | :---- |
| ngrok\_auth\_token | Your ngrok key. If running in Colab, it's best to leave this blank and pass the token via command line. |
| country\_code | The country code for numbers to search (e.g., us, ca, gb). |
| cache\_duration\_seconds | The interval (in seconds) for the background scraper to refresh data (default 300 seconds, or 5 minutes). |
| max\_workers | The maximum number of threads to use for concurrent number checking. |

## **💻 Execution Guide**

### **Mode 1: Local Execution**

Run main.py on your local machine.

\# Run the main application  
python main.py

* If ngrok\_auth\_token in config.toml is **empty**, the program starts in local mode only (http://127.0.0.1:5000).  
* If the token **is set**, both the Flask service and the ngrok public tunnel will be started.

### **Mode 2: Colab/Public Execution**

Use public.py, which is set up to read the ngrok token from command-line arguments, ideal for Colab Secrets.

**Colab Steps:**

1. Store your ngrok Authtoken in Colab's Secrets Manager, named NGROK\_AUTH\_TOKEN.  
2. In a Colab notebook cell, execute the following commands (Chrome installation is often necessary in Colab environments):

\# 1\. Ensure Chrome is installed (necessary for Colab environment)  
\!apt-get update  
\!wget https://dl.google.com/linux/direct/google-chrome-stable\_current\_amd64.deb  
\!apt install \--fix-broken \-y ./google-chrome-stable\_current\_amd64.deb

\# 2\. Run your Python application (reading token from Colab Secrets)  
from google.colab import userdata  
ng\_token=userdata.get("NGROK\_AUTH\_TOKEN")  
\!uv run python public.py \--ngrok\_token $ng\_token

## **💡 Optimization Summary**

The core performance issue in the original code was the repeated execution of **ChromeDriverManager().install()** inside the concurrent threads. This caused significant overhead.

| Aspect | Original Code (main.py/public.py) | Optimized Code (Revised) | Benefit |
| :---- | :---- | :---- | :---- |
| **Scraper Performance** | Repeated calls to ChromeDriverManager().install() in every thread. | **ChromeDriverManager().install() is now called only ONCE during startup.** | **Dramatically improved startup time and scraping efficiency.** Avoids unnecessary driver file checks and setup multiple times per cache update cycle. |

The revised files maintain the clear separation between local and Colab initialization while incorporating the critical performance fix.