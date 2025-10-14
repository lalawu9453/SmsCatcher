# **Temporary SMS Receiver Monitor**
<div align="center">

<img src="https://i.meee.com.tw/ikqBwaY.jpg" alt="Project Banner" style="border-radius: 10px; margin-top: 10px; margin-bottom: 10px;width: 300px; height: 300px;">

</div>

<p align="center">  
<strong>English</strong> •  
<a href="./README.md"><strong>繁體中文 (Traditional Chinese)</strong></a>  
</p>

This project is a Python application designed to scrape a specific website for temporary SMS receiver numbers. It uses **Selenium** to bypass anti-bot protections and a **ThreadPoolExecutor** for concurrent checking of multiple number pages to identify "active numbers" that have received a new SMS within the last hour.

![Demo GIF](demo.png)

It offers two execution modes:

1. **Local Execution (main.py)**: For running on your local machine, with the option to use ngrok for a public URL.  
2. **Colab Execution (main.py --ngrok_token $ng_token)**: Tailored for Google Colaboratory, enabling cloud execution and quick public URL tunneling via ngrok.

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

#### Run the main application  
`uv sync`

`uv run main.py`

* If ngrok\_auth\_token in config.toml is **empty**, the program starts in local mode only (http://127.0.0.1:5000).  
* If the token **is set**, both the Flask service and the ngrok public tunnel will be started.

### **Mode 2: Colab/Public Execution**
<a href="https://colab.research.google.com/github/LayorX/Temporary-SMS-Receiver-Monitor/blob/master/Temporary_SMS_Receiver_Monitor.ipynb" target="_blank"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>


[Execute Colab Easily](/Temporary_SMS_Receiver_Monitor.ipynb)


Use `!uv run python main.py --ngrok_token $ng_token`, which is set up to read the ngrok token from command-line arguments, ideal for Colab Secrets.
#### auto colab execute
**Colab Steps:**

1. Store your ngrok Authtoken in Colab's Secrets Manager, named NGROK\_AUTH\_TOKEN.  
2. In a Colab notebook cell, execute the following commands (Chrome installation is often necessary in Colab environments)

#### input code by yourself
```
# setting NGROK_AUTH_TOKEN
NGROK_AUTH_TOKEN = "" # @param {"type":"string","placeholder":"NGROK_AUTH_TOKEN"}

# clone
!git clone https://github.com/LayorX/Temporary-SMS-Receiver-Monitor.git
%cd Temporary-SMS-Receiver-Monitor
!apt-get update

# Download the stable version of the Google Chrome installer
!wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# Install the .deb file and fix dependency issues
!apt install --fix-broken -y ./google-chrome-stable_current_amd64.deb

from google.colab import userdata
from google.colab.userdata import NotebookAccessError,SecretNotFoundError

try:
  print("【NGROK_AUTH_TOKEN】: Secrets Manager")
  ng_token = userdata.get("NGROK_AUTH_TOKEN")
except (NotebookAccessError, SecretNotFoundError):
  print("【NGROK_AUTH_TOKEN】: Google Colab Code Block")
  ng_token = NGROK_AUTH_TOKEN

!uv sync
!uv run python main.py --ngrok_token $ng_token --web top2
```

## **💡 Optimization Summary**

The core performance issue in the original code was the repeated execution of **ChromeDriverManager().install()** inside the concurrent threads. This caused significant overhead.

| Aspect | Original Code (main.py) | Optimized Code (Revised) | Benefit |
| :---- | :---- | :---- | :---- |
| **Scraper Performance** | Repeated calls to ChromeDriverManager().install() in every thread. | **ChromeDriverManager().install() is now called only ONCE during startup.** | **Dramatically improved startup time and scraping efficiency.** Avoids unnecessary driver file checks and setup multiple times per cache update cycle. |

The revised files maintain the clear separation between local and Colab initialization while incorporating the critical performance fix.


## **💖 Contributing**

This is an open-source project, and contributions of all kinds are welcome\! **Whether you are an experienced developer or a newcomer, your help is appreciated in making this tool even better\!**

### [**👉Contributing**](./CONTRIBUTING.md) 

We will review your contribution as soon as possible. Thank you to everyone who dedicates their time and effort to this project\!

## **📄 License**

This project is licensed under the [MIT License](https://www.google.com/search?q=./LICENSE).