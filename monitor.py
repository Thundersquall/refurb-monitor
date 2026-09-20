import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup
import os
import time

# 从 GitHub Secrets 读取环境变量
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.do_GET()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

APPLE_REFURB_URL = "https://www.apple.com/jp/shop/refurbished/iphone"
BASE_URL = "https://www.apple.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
}

def send_push(title: str, body: str, url: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过推送")
        return
        
    tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": f"🚨 *{title}*\n\n{body}\n\n[点击立即前往抢购]({url})",
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(tg_url, json=payload, timeout=10)
        print(f"推送结果: {r.status_code}")
    except Exception as e:
        print(f"Telegram 推送失败: {e}")

def check_stock():
    try:
        resp = requests.get(APPLE_REFURB_URL, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"官网响应异常: HTTP {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        products_found = []
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            title = a_tag.get_text(strip=True)
            
            # 只锁定 128GB 和 256GB，排除大容量刺客与 Pro Max
            target_capacities = ["128GB", "256GB"]
            has_target_capacity = any(cap in title for cap in target_capacities)
            
            if "/jp/shop/product/" in href and "16 Pro" in title and "Pro Max" not in title and has_target_capacity:
                full_link = BASE_URL + href if href.startswith("/") else href
                products_found.append({"title": title, "url": full_link})

        return products_found
    except Exception as e:
        print(f"抓取异常: {e}")
        return []

if __name__ == "__main__":
    # 后台启动假端口，供 Render 存活检测通过
    threading.Thread(target=run_health_server, daemon=True).start()
    print("监控服务已启动，进入 24 小时轮询模式...")
    
    notified_urls = set()  # 记录已经通知过的商品链接，避免每 30 秒轰炸

    while True:
        try:
            items = check_stock()
            current_urls = {item['url'] for item in items}

            # 筛选出当前轮次“新上架”的机器
            new_items = [item for item in items if item['url'] not in notified_urls]

            if new_items:
                print(f"🎯 发现新现货: {len(new_items)} 款 (总库存: {len(items)} 款)")
                
                # 拼接多款商品的直达列表
                lines = []
                for idx, item in enumerate(new_items[:8], 1):  # 最多展示前 8 款，防止消息过长
                    lines.append(f"{idx}. [{item['title']}]({item['url']})")
                
                body_text = "\n".join(lines)
                if len(new_items) > 8:
                    body_text += f"\n...等共 {len(new_items)} 款新上架！"

                send_push(
                    title=f"🔥 Apple 官网 16 Pro 上架 ({len(new_items)} 款新货)",
                    body=body_text,
                    url=new_items[0]['url']
                )

            # 更新已通知集合（自动清理已经卖完下架的机器）
            notified_urls = current_urls

            if not items:
                print("暂无 16 Pro 库存。")

        except Exception as e:
            print(f"检测循环发生异常: {e}")

        # 30 秒轮询一次
        time.sleep(30)
