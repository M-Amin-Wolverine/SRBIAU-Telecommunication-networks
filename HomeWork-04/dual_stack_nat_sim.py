#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DualStackNATSimulator v3.0 - Ultimate Edition
--------------------------------------------
Simulates IPv4/IPv6 performance in mixed NAT environments with advanced features:
- Multithreaded traffic simulation for speed
- Real-time performance monitoring
- Interactive Plotly visualizations
- Detailed logging with timestamps
- Command-line interface for customization
- Enhanced metrics and statistical analysis
- Support for custom traffic profiles
"""

import sys
import subprocess
import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import numpy as np
import pandas as pd
from scipy import stats
import random
from scapy.all import IP, IPv6, ICMP, ICMPv6EchoRequest, send
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import psutil  # For system resource monitoring
import yaml  # For configuration files

# --- Auto-install required packages ---
required_libs = ["numpy", "scipy", "pandas", "plotly", "scapy", "psutil", "pyyaml"]
for lib in required_libs:
    try:
        __import__(lib)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("simulation.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DualStackNATSimulator:
    """
    Advanced dual-stack (IPv4/IPv6) network simulator with NAT, congestion, and censorship modeling.
    """
    def __init__(self, config_file="config.yaml"):
        """
        Initialize simulator with parameters from a YAML config file.
        """
        self.load_config(config_file)
        self.ipv6_users = int(self.num_users * self.ipv6_adoption)
        self.ipv4_users = self.num_users - self.ipv6_users
        self.results_queue = Queue()
        self.start_time = time.time()
        logger.info(f"Initialized simulator with {self.num_users} users, {self.ipv6_adoption*100}% IPv6 adoption")

    def load_config(self, config_file):
        """Load configuration from YAML file or set defaults."""
        defaults = {
            'num_users': 5000,
            'ipv6_adoption': 0.05,
            'nat_users_per_ip': 64,
            'base_latency_ipv4': 20,
            'base_latency_ipv6': 15,
            'packet_loss_nat': 0.02,
            'censorship_throttle': 0.1,
            'congestion_probability': 0.15,
            'jitter_factor': 0.2,
            'max_threads': 8,
            'traffic_profiles': {
                'http': {'latency_scale': 1.0, 'throughput_min': 15, 'throughput_max': 60},
                'video': {'latency_scale': 1.2, 'throughput_min': 20, 'throughput_max': 100},
                'censored': {'latency_scale': 1.5, 'throughput_min': 5, 'throughput_max': 30}
            }
        }
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f) or defaults
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found, using defaults")
            config = defaults
        for key, value in defaults.items():
            setattr(self, key, config.get(key, value))

    def simulate_user_traffic(self, user_id, traffic_type):
        """Simulate traffic for a single user."""
        profile = self.traffic_profiles[traffic_type]
        if random.random() < self.ipv6_users / self.num_users:
            # IPv6 route
            latency = np.random.normal(self.base_latency_ipv6 * profile['latency_scale'], 5)
            throughput = random.uniform(profile['throughput_min'], profile['throughput_max'])
            if traffic_type == 'censored':
                throughput *= (1 - self.censorship_throttle)
            drop = False
        else:
            # IPv4/NAT route
            latency = np.random.normal(self.base_latency_ipv4 * profile['latency_scale'] + random.uniform(5, 15), 10)
            throughput = random.uniform(profile['throughput_min'] / 2, profile['throughput_max'] / 2)
            drop = random.random() < self.packet_loss_nat
            if user_id % self.nat_users_per_ip == 0:
                throughput *= 0.6
            if random.random() < self.congestion_probability:
                latency *= 1.5
                throughput *= 0.7
        latency *= (1 + random.uniform(-self.jitter_factor, self.jitter_factor))
        return {
            'user_id': user_id,
            'latency_ms': latency if not drop else np.inf,
            'throughput_mbps': max(0, throughput),
            'dropped': drop,
            'protocol': 'IPv6' if user_id < self.ipv6_users else 'IPv4',
            'traffic_type': traffic_type
        }

    def simulate_traffic(self, traffic_type='http', duration=60):
        """Simulate traffic for all users using multithreading."""
        logger.info(f"Simulating {traffic_type} traffic for {self.num_users} users...")
        results = []
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = [
                executor.submit(self.simulate_user_traffic, i, traffic_type)
                for i in range(self.num_users)
            ]
            for future in futures:
                results.append(future.result())
        latencies = [r['latency_ms'] for r in results if not r['dropped']]
        throughputs = [r['throughput_mbps'] for r in results]
        drops = sum(1 for r in results if r['dropped'])
        return {
            'avg_latency_ms': np.mean(latencies) if latencies else np.inf,
            'avg_throughput_mbps': np.mean(throughputs),
            'drop_rate': drops / self.num_users,
            'ipv6_efficiency_gain': (self.base_latency_ipv4 - np.mean(latencies)) / self.base_latency_ipv4 * 100
            if latencies else 0,
            'raw_results': results
        }

    def run_multiple_scenarios(self, scenarios=10):
        """Run multiple traffic scenarios with real-time monitoring."""
        results = []
        for i in range(scenarios):
            traffic_type = random.choice(list(self.traffic_profiles.keys()))
            result = self.simulate_traffic(traffic_type=traffic_type)
            result['scenario'] = i + 1
            result['traffic_type'] = traffic_type
            result['cpu_usage'] = psutil.cpu_percent()
            result['memory_usage_mb'] = psutil.virtual_memory().used / 1024 / 1024
            results.append(result)
            logger.info(f"Scenario {i+1} completed: {traffic_type}, Latency={result['avg_latency_ms']:.2f}ms, "
                        f"Throughput={result['avg_throughput_mbps']:.2f}Mbps, Drops={result['drop_rate']*100:.2f}%")
            self.results_queue.put(result)
        return results

    def visualize_results(self, results):
        """Create interactive Plotly visualizations."""
        df = pd.DataFrame([{
            'scenario': r['scenario'],
            'avg_latency_ms': r['avg_latency_ms'],
            'avg_throughput_mbps': r['avg_throughput_mbps'],
            'drop_rate': r['drop_rate'],
            'traffic_type': r['traffic_type']
        } for r in results])

        # Plot 1: Latency and Throughput Trends
        fig = make_subplots(rows=2, cols=1, subplot_titles=("Average Latency per Scenario", "Average Throughput per Scenario"))
        for t in self.traffic_profiles.keys():
            df_t = df[df['traffic_type'] == t]
            fig.add_trace(
                go.Scatter(x=df_t['scenario'], y=df_t['avg_latency_ms'], mode='lines+markers', name=f'Latency ({t})'),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=df_t['scenario'], y=df_t['avg_throughput_mbps'], mode='lines+markers', name=f'Throughput ({t})'),
                row=2, col=1
            )
        fig.update_layout(title="Network Performance Trends", showlegend=True)
        fig.update_xaxes(title_text="Scenario #", row=2, col=1)
        fig.update_yaxes(title_text="Latency (ms)", row=1, col=1)
        fig.update_yaxes(title_text="Throughput (Mbps)", row=2, col=1)
        fig.write_html("performance_trends.html")
        logger.info("📊 Performance trends saved to 'performance_trends.html'")

        # Plot 2: Throughput Distribution
        fig2 = go.Figure()
        for t in self.traffic_profiles.keys():
            df_t = df[df['traffic_type'] == t]
            fig2.add_trace(go.Histogram(x=df_t['avg_throughput_mbps'], name=f'Throughput ({t})', opacity=0.6))
        fig2.update_layout(title="Throughput Distribution", barmode='overlay', xaxis_title="Throughput (Mbps)", yaxis_title="Frequency")
        fig2.write_html("throughput_distribution.html")
        logger.info("📊 Throughput distribution saved to 'throughput_distribution.html'")

    def test_icmp_reachability(self):
        """Test ICMP reachability for IPv4 and IPv6."""
        try:
            logger.info("🔹 Sending test ICMP packets (may require sudo privileges)...")
            send(IP(dst="192.168.1.1") / ICMP(), verbose=False)
            send(IPv6(dst="2001:db8::1") / ICMPv6EchoRequest(), verbose=False)
            logger.info("✅ ICMP tests sent successfully")
        except PermissionError:
            logger.warning("⚠️ ICMP send skipped (run as sudo to test)")

def main():
    """Main execution with command-line arguments."""
    parser = argparse.ArgumentParser(description="DualStackNATSimulator v3.0")
    parser.add_argument('--users', type=int, default=5000, help="Number of users to simulate")
    parser.add_argument('--ipv6', type=float, default=0.05, help="IPv6 adoption rate (0 to 1)")
    parser.add_argument('--scenarios', type=int, default=10, help="Number of scenarios to run")
    parser.add_argument('--config', type=str, default="config.yaml", help="Path to YAML config file")
    args = parser.parse_args()

    # Create default config file if not exists
    if not os.path.exists(args.config):
        default_config = {
            'num_users': args.users,
            'ipv6_adoption': args.ipv6,
            'nat_users_per_ip': 64,
            'base_latency_ipv4': 20,
            'base_latency_ipv6': 15,
            'packet_loss_nat': 0.02,
            'censorship_throttle': 0.1,
            'congestion_probability': 0.15,
            'jitter_factor': 0.2,
            'max_threads': 8,
            'traffic_profiles': {
                'http': {'latency_scale': 1.0, 'throughput_min': 15, 'throughput_max': 60},
                'video': {'latency_scale': 1.2, 'throughput_min': 20, 'throughput_max': 100},
                'censored': {'latency_scale': 1.5, 'throughput_min': 5, 'throughput_max': 30}
            }
        }
        with open(args.config, 'w') as f:
            yaml.dump(default_config, f)
        logger.info(f"Created default config file at {args.config}")

    # Initialize and run simulator
    sim = DualStackNATSimulator(config_file=args.config)
    sim.num_users = args.users
    sim.ipv6_adoption = args.ipv6
    results = sim.run_multiple_scenarios(scenarios=args.scenarios)

    # Save results to CSV
    df = pd.DataFrame(results)
    df.drop(columns=['raw_results']).to_csv("simulation_results.csv", index=False)
    logger.info("📁 Results saved to 'simulation_results.csv'")

    # Visualize results
    sim.visualize_results(results)

    # Test ICMP reachability
    sim.test_icmp_reachability()

    # Generate chart for latency trends
    df_chart = pd.DataFrame([{
        'scenario': r['scenario'],
        'avg_latency_ms': r['avg_latency_ms'],
        'traffic_type': r['traffic_type']
    } for r in results])
    ```chartjs
    {
      "type": "line",
      "data": {
        "labels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "datasets": [
          {
            "label": "HTTP Latency",
            "data": [df_chart[df_chart['traffic_type'] == 'http']['avg_latency_ms'].tolist()],
            "borderColor": "#1f77b4",
            "backgroundColor": "rgba(31, 119, 180, 0.2)",
            "fill": true
          },
          {
            "label": "Video Latency",
            "data": [df_chart[df_chart['traffic_type'] == 'video']['avg_latency_ms'].tolist()],
            "borderColor": "#ff7f0e",
            "backgroundColor": "rgba(255, 127, 14, 0.2)",
            "fill": true
          },
          {
            "label": "Censored Latency",
            "data": [df_chart[df_chart['traffic_type'] == 'censored']['avg_latency_ms'].tolist()],
            "borderColor": "#d62728",
            "backgroundColor": "rgba(214, 39, 40, 0.2)",
            "fill": true
          }
        ]
      },
      "options": {
        "responsive": true,
        "plugins": {
          "title": {
            "display": true,
            "text": "Latency Trends by Traffic Type"
          },
          "legend": {
            "position": "top"
          }
        },
        "scales": {
          "x": {
            "title": {
              "display": true,
              "text": "Scenario #"
            }
          },
          "y": {
            "title": {
              "display": true,
              "text": "Latency (ms)"
            },
            "beginAtZero": true
          }
        }
      }
    }
if name == "main":
main()
