import os
import requests
from bs4 import BeautifulSoup

# 从 GitHub Secrets 读取环境变量
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

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
    print("开始检测 Apple 官网 16 Pro 官翻库存...")
    items = check_stock()
    
    if items:
        print(f"🎯 发现现货: {len(items)} 款")
        first_item = items[0]
        send_push(
            title="🔥 Apple 官网 16 Pro 官翻有货了！",
            body=f"型号: {first_item['title']}\n共 {len(items)} 款可选，手慢无！",
            url=first_item['url']
        )
    else:
        print("暂无 16 Pro 库存。")
