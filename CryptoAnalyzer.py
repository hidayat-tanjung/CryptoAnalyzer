import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import time
import os
import json
import logging
from typing import List, Dict, Optional, Union

class CryptoAnalyzer:
    def __init__(self, debug=False):
        """Initialize CryptoAnalyzer with logging and cache setup"""
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "CryptoAnalysisTool/3.0"
        }
        self.coin_data_cache = {}
        self.alert_conditions = []
        self.debug = debug
        self.symbol_to_id = {}  # Dictionary to map symbols to IDs
        
        # Setup infrastructure
        self._setup_directories()
        self._setup_logging()
        self._load_coin_list()
        
        self._log("CryptoAnalyzer initialized successfully", "info")

    def _setup_directories(self):
        """Create required directories"""
        try:
            os.makedirs(".cache", exist_ok=True)
            os.makedirs("logs", exist_ok=True)
            os.makedirs("exports", exist_ok=True)
            self._log("Directories created", "debug")
        except Exception as e:
            self._log(f"Failed to create directories: {str(e)}", "error")

    def _setup_logging(self):
        """Configure logging system"""
        try:
            self.logger = logging.getLogger("CryptoAnalyzer")
            self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
            
            # Clear existing handlers
            if self.logger.hasHandlers():
                self.logger.handlers.clear()
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # File handler
            file_handler = logging.FileHandler("logs/crypto_analysis.log")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Console handler (only in debug mode)
            if self.debug:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)
                
        except Exception as e:
            print(f"Failed to setup logging: {str(e)}")

    def _load_coin_list(self):
        """Load coin list and create symbol to ID mapping"""
        cache_file = ".cache/coin_list.json"
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    coins = json.load(f)
            else:
                coins = self._make_api_request("coins/list")
                if coins:
                    with open(cache_file, 'w') as f:
                        json.dump(coins, f)
            
            if coins:
                self.symbol_to_id = {coin['symbol'].lower(): coin['id'] for coin in coins}
                # Add common exceptions
                self.symbol_to_id['xrp'] = 'ripple'
                self.symbol_to_id['ada'] = 'cardano'
                self.symbol_to_id['doge'] = 'dogecoin'
                
        except Exception as e:
            self._log(f"Failed to load coin list: {str(e)}", "error")

    def _log(self, message: str, level: str = "info"):
        """Internal logging method"""
        if not hasattr(self, 'logger'):
            print(f"[{level.upper()}] {message}")
            return
            
        if level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.info(message)

    def _make_api_request(self, endpoint: str, params: Optional[Dict] = None):
        """Make API request with error handling"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self._log(f"API request failed to {url}: {str(e)}", "error")
            return None

    def get_top_coins(self, limit: int = 10) -> Optional[pd.DataFrame]:
        """
        Get top cryptocurrencies by market cap
        
        Args:
            limit (int): Number of coins to return
            
        Returns:
            DataFrame: Contains columns: 
                ['id', 'symbol', 'name', 'current_price', 
                 'market_cap', 'price_change_percentage_24h']
        """
        cache_key = f"top_{limit}_coins"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": False
        }
        
        data = self._make_api_request("coins/markets", params)
        if data:
            df = pd.DataFrame(data)
            return df[['id', 'symbol', 'name', 'current_price', 
                      'market_cap', 'price_change_percentage_24h']]
        return None

    def display_top_coins(self, limit: int = 10):
        """
        Display top cryptocurrencies in a formatted table
        
        Args:
            limit (int): Number of coins to display
        """
        print(f"\n{'='*40}")
        print(f"TOP {limit} CRYPTOCURRENCIES BY MARKET CAP")
        print(f"{'='*40}")
        
        top_coins = self.get_top_coins(limit)
        if top_coins is None:
            print("Failed to retrieve data")
            return
            
        # Format table header
        print("\n{:<4} {:<8} {:<20} {:<12} {:<18} {:<10}".format(
            "Rank", "Symbol", "Name", "Price (USD)", "Market Cap", "24h %"
        ))
        print("-"*80)
        
        # Format each row
        for i, (_, row) in enumerate(top_coins.iterrows(), 1):
            print("{:<4} {:<8} {:<20} ${:<11,.2f} ${:<17,.0f} {:<10.2f}%".format(
                i,
                row['symbol'].upper(),
                row['name'],
                row['current_price'],
                row['market_cap'],
                row['price_change_percentage_24h']
            ))
        
        # Add timestamp
        print(f"\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Export option
        export = input("\nExport to CSV? (y/n): ").lower()
        if export == 'y':
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exports/top_{limit}_coins_{timestamp}.csv"
            top_coins.to_csv(filename, index=False)
            print(f"Data exported to {filename}")

    def get_coin_id(self, input_str: str) -> Optional[str]:
        """Convert user input (symbol or ID) to CoinGecko ID"""
        input_lower = input_str.lower()
        
        # Check if input is a known symbol
        if input_lower in self.symbol_to_id:
            return self.symbol_to_id[input_lower]
        
        # Check if input is already a valid ID
        test_data = self.get_coin_history(input_lower, days=1)
        if test_data is not None:
            return input_lower
        
        return None

    def get_coin_history(self, coin_id: str, days: int = 90) -> Optional[pd.DataFrame]:
        """Get historical price data for a specific coin"""
        endpoint = f"coins/{coin_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": days
        }
        
        data = self._make_api_request(endpoint, params)
        if data:
            prices = pd.DataFrame(data['prices'], columns=['timestamp', 'price'])
            volumes = pd.DataFrame(data['total_volumes'], columns=['timestamp', 'volume'])
            
            df = prices.merge(volumes, on='timestamp')
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.drop('timestamp', axis=1, inplace=True)
            
            return df
        return None

    def calculate_technical_indicators(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Calculate technical indicators for price data"""
        if df is None or df.empty:
            return None
            
        try:
            # Moving Averages
            df['MA_7'] = df['price'].rolling(window=7).mean()
            df['MA_30'] = df['price'].rolling(window=30).mean()
            
            # RSI
            delta = df['price'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            return df
            
        except Exception as e:
            self._log(f"Technical indicator calculation failed: {str(e)}", "error")
            return None

    def live_analysis(self, coin_id: str, interval: int = 60, duration: int = 3600):
        """
        Real-time price analysis with auto-refresh
        
        Args:
            coin_id (str): CoinGecko ID of the cryptocurrency
            interval (int): Refresh interval in seconds (default: 60)
            duration (int): Total analysis duration in seconds (default: 3600)
        """
        start_time = time.time()
        plt.ion()  # Turn on interactive mode
        fig = plt.figure(figsize=(14, 7))
        
        try:
            while time.time() - start_time < duration:
                plt.clf()  # Clear previous frame
                
                # Get fresh data
                df = self.get_coin_history(coin_id, days=1)
                if df is None:
                    self._log(f"Failed to get data for {coin_id}", "warning")
                    time.sleep(interval)
                    continue
                    
                df = self.calculate_technical_indicators(df)
                
                if df is None:
                    self._log("Failed to calculate indicators", "warning")
                    time.sleep(interval)
                    continue
                
                # Plot data
                plt.plot(df['date'], df['price'], label='Price', color='blue', linewidth=2)
                plt.plot(df['date'], df['MA_7'], 
                        label='7-Min MA' if interval < 1440 else '7-Day MA', 
                        color='orange', linestyle='--')
                plt.plot(df['date'], df['MA_30'], 
                        label='30-Min MA' if interval < 1440 else '30-Day MA', 
                        color='green', linestyle='-.')
                
                # Current price annotation
                current_price = df['price'].iloc[-1]
                plt.annotate(f'${current_price:,.2f}', 
                            xy=(df['date'].iloc[-1], current_price),
                            xytext=(10, 10), textcoords='offset points',
                            bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.5),
                            arrowprops=dict(arrowstyle='->'))
                
                # Formatting
                plt.title(f"{coin_id.upper()} Live Analysis (Updated: {datetime.now().strftime('%H:%M:%S')})")
                plt.xlabel("Time")
                plt.ylabel("Price (USD)")
                plt.legend()
                plt.grid(True)
                
                # Refresh
                plt.draw()
                plt.pause(0.1)
                
                # Calculate remaining sleep time accounting for processing time
                elapsed = time.time() - start_time
                remaining_sleep = max(1, interval - (elapsed % interval))
                time.sleep(remaining_sleep)
                
        except KeyboardInterrupt:
            print("\nLive analysis stopped by user")
        except Exception as e:
            self._log(f"Live analysis error: {str(e)}", "error")
        finally:
            plt.ioff()
            plt.close(fig)

    def analyze_coin(self, coin_input: str, days: int = 90):
        """Display analysis for a specific cryptocurrency"""
        coin_id = self.get_coin_id(coin_input)
        if coin_id is None:
            print(f"\nInvalid coin identifier: '{coin_input}'")
            print("Please use either:")
            print("- CoinGecko ID (e.g. 'bitcoin', 'ripple')")
            print("- Symbol (e.g. 'BTC', 'XRP')")
            print("\nCommon examples:")
            print("XRP -> ripple")
            print("ADA -> cardano")
            print("DOGE -> dogecoin")
            return
            
        print(f"\nAnalyzing {coin_id.upper()}...")
        
        # Get historical data
        history = self.get_coin_history(coin_id, days)
        if history is None:
            print("Failed to get historical data")
            return
            
        # Calculate indicators
        analyzed_data = self.calculate_technical_indicators(history)
        if analyzed_data is None:
            print("Failed to calculate indicators")
            return
            
        # Display summary
        print("\n=== SUMMARY ===")
        print(f"Current Price: ${analyzed_data['price'].iloc[-1]:,.2f}")
        print(f"24h Volume: ${analyzed_data['volume'].iloc[-1]:,.0f}")
        print(f"30-Day High: ${analyzed_data['price'].max():,.2f}")
        print(f"30-Day Low: ${analyzed_data['price'].min():,.2f}")
        print(f"Current RSI: {analyzed_data['RSI'].iloc[-1]:.2f}")
        
        # Plot data
        plt.figure(figsize=(14, 7))
        
        # Price and MAs
        plt.plot(analyzed_data['date'], analyzed_data['price'], label='Price')
        plt.plot(analyzed_data['date'], analyzed_data['MA_7'], label='7-Day MA')
        plt.plot(analyzed_data['date'], analyzed_data['MA_30'], label='30-Day MA')
        
        plt.title(f"{coin_id.upper()} Price Analysis")
        plt.xlabel("Date")
        plt.ylabel("Price (USD)")
        plt.legend()
        plt.grid()
        plt.show()

# Main Program
if __name__ == "__main__":
    analyzer = CryptoAnalyzer(debug=True)
    # Main Program
if __name__ == "__main__":
    analyzer = CryptoAnalyzer(debug=True)
    
    # Contoh penggunaan langsung live_analysis (uncomment untuk digunakan)
    # analyzer.live_analysis('bitcoin', interval=30, duration=1800)  # Update setiap 30 detik selama 30 menit
    
    while True:
        print("\n=== CRYPTO ANALYZER ===")
        print("1. View Top Cryptocurrencies")
        print("2. Analyze Specific Coin (Historical)")
        print("3. Live Coin Analysis")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ")
        
        if choice == "1":
            try:
                limit = int(input("Number of coins to display (default 10): ") or 10)
                analyzer.display_top_coins(limit)
            except ValueError:
                print("Please enter a valid number")
                
        elif choice == "2":
            coin_input = input("Enter coin ID/symbol: ").strip()
            if coin_input:
                analyzer.analyze_coin(coin_input)
                
        elif choice == "3":
            coin_input = input("Enter coin ID/symbol for live analysis: ").strip()
            if coin_input:
                try:
                    interval = int(input("Update interval in seconds (default 60): ") or 60)
                    duration = int(input("Total duration in seconds (default 3600): ") or 3600)
                    coin_id = analyzer.get_coin_id(coin_input)
                    if coin_id:
                        analyzer.live_analysis(coin_id, interval, duration)
                    else:
                        print(f"Invalid coin identifier: {coin_input}")
                except ValueError:
                    print("Please enter valid numbers")
                    
        elif choice == "4":
            print("Exiting program...")
            break
            
        else:
            print("Invalid choice, please try again")
    
    while True:
        print("\n=== CRYPTO ANALYZER ===")
        print("1. View Top Cryptocurrencies")
        print("2. Analyze Specific Coin (Historical)")
        print("3. Live Coin Analysis")
        print("4. Exit")
        
        choice = input("\nSelect option (1-4): ")
        
        if choice == "1":
            try:
                limit = int(input("Number of coins to display (default 10): ") or 10)
                analyzer.display_top_coins(limit)
            except ValueError:
                print("Please enter a valid number")
                
        elif choice == "2":
            coin_input = input("Enter coin ID/symbol: ").strip()
            if coin_input:
                analyzer.analyze_coin(coin_input)
                
        elif choice == "3":
            coin_input = input("Enter coin ID/symbol for live analysis: ").strip()
            if coin_input:
                try:
                    interval = int(input("Update interval in seconds (default 60): ") or 60)
                    duration = int(input("Total duration in seconds (default 3600): ") or 3600)
                    coin_id = analyzer.get_coin_id(coin_input)
                    if coin_id:
                        analyzer.live_analysis(coin_id, interval, duration)
                    else:
                        print(f"Invalid coin identifier: {coin_input}")
                except ValueError:
                    print("Please enter valid numbers")
                    
        elif choice == "4":
            print("Exiting program...")
            break
            
        else:
            print("Invalid choice, please try again")
