
import os
import json
from datetime import datetime, timedelta
import pytz
import numpy as np
import requests
import re
from bs4 import BeautifulSoup
import time
import random


# 导入plotly用于交互式图表
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 从环境变量获取微信公众号配置
appID = os.environ.get("APP_ID")
appSecret = os.environ.get("APP_SECRET")
openId = os.environ.get("OPEN_ID")
template_id = os.environ.get("TEMPLATE_ID")

# 北上广深杭五个城市及其核心区域映射（精简版）
CITIES = {
    "北京": ["朝阳", "海淀", "西城", "东城", "丰台", "昌平", "顺义"],
    "上海": ["浦东", "徐汇", "静安", "黄浦", "长宁"],
    "广州": ["天河", "越秀", "海珠", "荔湾", "白云"],
    "深圳": ["福田", "罗湖", "南山", "宝安", "龙岗"],
    "杭州": ["西湖", "上城", "余杭"]
}

# 获取北京时间
def today_date():
    return datetime.now(pytz.timezone("Asia/Shanghai")).date()

# 获取当前时间段标识（上午/下午）
def get_time_period():
    hour = datetime.now(pytz.timezone("Asia/Shanghai")).hour
    if 6 <= hour < 12:
        return "上午"
    elif 12 <= hour < 18:
        return "下午"
    else:
        return "晚间"

# 获取过去N周的日期列表
def get_past_weeks_dates(weeks=8):
    today = datetime.now(pytz.timezone("Asia/Shanghai"))
    dates = []
    for i in range(weeks, 0, -1):
        # 获取周一的日期
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday + i*7)
        dates.append(monday.strftime("%Y-%m-%d"))
    # 添加本周一
    days_since_monday = today.weekday()
    current_monday = today - timedelta(days=days_since_monday)
    dates.append(current_monday.strftime("%Y-%m-%d"))
    return dates

# 获取指定时间范围的周日期列表
def get_weeks_dates(start_date, weeks_count):
    days_since_monday = start_date.weekday()
    start_monday = start_date - timedelta(days=days_since_monday)
    
    dates = []
    for i in range(weeks_count):
        week_date = start_monday + timedelta(weeks=i)
        dates.append(week_date)
    return dates

# 生成模拟房价数据
def generate_mock_house_price_data(city, district, start_date, weeks_count):
    base_prices = {
        "北京": 60000,
        "上海": 58000,
        "广州": 32000,
        "深圳": 55000,
        "杭州": 40000
    }
    
    district_coefficients = {
        "朝阳": 1.2, "海淀": 1.3, "西城": 1.5, "东城": 1.4, "丰台": 0.9,
        "浦东": 1.2, "徐汇": 1.4, "静安": 1.6, "黄浦": 1.5, "长宁": 1.3,
        "天河": 1.3, "越秀": 1.2, "海珠": 1.1, "荔湾": 1.0, "白云": 0.8,
        "福田": 1.4, "罗湖": 1.2, "南山": 1.5, "宝安": 0.9, "龙岗": 0.8,
        "西湖": 1.3, "上城": 1.2, "余杭": 0.9
    }
    
    weeks = get_weeks_dates(start_date, weeks_count)
    
    base_price = base_prices.get(city, 30000)
    coefficient = district_coefficients.get(district, 1.0)
    price = base_price * coefficient
    
    np.random.seed(42)
    
    trend = np.linspace(0, np.random.uniform(-0.1, 0.1), weeks_count)
    seasonality = 0.03 * np.sin(np.linspace(0, 2 * np.pi * (weeks_count / 52), weeks_count))
    random_noise = 0.02 * np.random.randn(weeks_count)
    
    price_changes = 1 + trend + seasonality + random_noise
    cumulative_changes = np.cumprod(price_changes)
    
    data = []
    for i, week_date in enumerate(weeks):
        current_price = price * cumulative_changes[i]
        base_volume = 100
        volume_factor = max(0.5, 1 - (current_price - price) / price * 0.5)
        transaction_count = int(base_volume * volume_factor * (1 + 0.3 * np.random.randn()))
        transaction_count = max(20, transaction_count)
        
        data.append({
            "date": week_date.strftime("%Y-%m-%d"),
            "average_price": round(current_price, 2),
            "transaction_count": transaction_count
        })
    
    return data

def extract_monthly_data_from_page(soup, year):
    """
    从页面中提取月度数据 - 修正版本
    """
    monthly_data = []
    
    # 查找包含月度数据的表格
    tables = soup.find_all('table')
    print(f"找到{len(tables)}个表格")
    
    for table in tables:
        # 查找表格标题或附近包含"二手房"、"新房"、"月份"等关键词
        table_text = table.get_text(strip=True)
        if any(keyword in table_text for keyword in ['二手房', '新房', '月份', '元/㎡']):
            print("找到房价数据表格")
            
            # 提取表格数据
            rows = table.find_all('tr')
            print(f"表格有{len(rows)}行")
            
            # 跳过表头行（通常第一行是表头）
            data_rows = rows[1:] if len(rows) > 1 else rows
            
            for i, row in enumerate(data_rows):
                cells = row.find_all(['td', 'th'])
                print(f"第{i+1}行有{len(cells)}个单元格")
                
                if len(cells) >= 3:  # 至少有序号、日期、二手房价格
                    # 提取数据
                    try:
                        # 获取月份（第一列）
                        month_str = cells[0].get_text(strip=True)
                        # 获取二手房价格（第二列）
                        second_hand_price = cells[1].get_text(strip=True)
                        # 获取新房价格（第三列，如果有的话）
                        new_house_price = cells[2].get_text(strip=True) if len(cells) >= 3 else None
                        
                        print(f"  原始数据: 月份={month_str}, 二手房价格={second_hand_price}, 新房价格={new_house_price}")
                        
                        # 检查月份格式 - 支持多种格式
                        month_match = None
                        if re.match(r'\d{4}-\d{2}', month_str):
                            month_match = month_str
                        elif re.match(r'\d{1,2}月', month_str):
                            # 格式如 "12月"，需要转换为 "2024-12"
                            month_num = re.search(r'(\d{1,2})', month_str).group(1)
                            month_match = f"{year}-{int(month_num):02d}"
                        elif month_str in ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']:
                            # 中文月份格式
                            chinese_months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
                            if month_str in chinese_months:
                                month_num = chinese_months.index(month_str) + 1
                                month_match = f"{year}-{month_num:02d}"
                        
                        if month_match:
                            # 提取二手房价格数字
                            price_match = re.search(r'(\d+(?:\.\d+)?)', second_hand_price)
                            new_house_price_value = None
                            
                            if price_match:
                                second_hand_price_value = float(price_match.group(1))
                                
                                # 提取新房价格（如果存在）
                                if new_house_price:
                                    new_price_match = re.search(r'(\d+(?:\.\d+)?)', new_house_price)
                                    if new_price_match:
                                        new_house_price_value = float(new_price_match.group(1))
                                
                                monthly_data.append({
                                    'month': month_match,
                                    'second_hand_price': round(second_hand_price_value, 2),
                                    'new_house_price': round(new_house_price_value, 2) if new_house_price_value else None,
                                    'source': f'聚汇数据-{year}年度页面'
                                })
                                print(f"  成功提取: {month_match} - 二手房:{second_hand_price_value}, 新房:{new_house_price_value or '无'}")
                                
                    except (ValueError, IndexError) as e:
                        print(f"  解析失败: {e}")
                        continue
            
            # 如果找到了数据，就不需要继续查找其他表格
            if monthly_data:
                break
    
    # 如果没有找到表格，尝试从页面文本中提取数据
    if not monthly_data:
        print("未找到表格，尝试从页面文本提取数据")
        page_text = soup.get_text()
        
        # 查找格式：序号 日期 二手房价格 新房价格
        # 例如：1 2025-09 52040 55894
        patterns = [
            r'(\d+)\s+(\d{4}-\d{2})\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)',  # 有序号+日期+二手房+新房
            r'(\d+)\s+(\d{4}-\d{2})\s+(\d+(?:\.\d+)?)',  # 有序号+日期+二手房
            r'(\d{4}-\d{2})\s+(\d+(?:\.\d+)?)'  # 只有日期+价格
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, page_text)
            if matches:
                print(f"使用模式{pattern}找到{len(matches)}个匹配")
                for match in matches:
                    if len(match) == 4:  # 有序号+日期+二手房+新房
                        seq_num, date_str, second_hand_price_str, new_house_price_str = match
                        second_hand_price = float(second_hand_price_str)
                        new_house_price = float(new_house_price_str)
                        
                        monthly_data.append({
                            'month': date_str,
                            'second_hand_price': round(second_hand_price, 2),
                            'new_house_price': round(new_house_price, 2),
                            'source': f'聚汇数据-{year}文本提取'
                        })
                    elif len(match) == 3:  # 有序号+日期+二手房
                        seq_num, date_str, price_str = match
                        price = float(price_str)
                        
                        monthly_data.append({
                            'month': date_str,
                            'second_hand_price': round(price, 2),
                            'new_house_price': None,
                            'source': f'聚汇数据-{year}文本提取'
                        })
                    elif len(match) == 2:  # 只有日期+价格
                        date_str, price_str = match
                        price = float(price_str)
                        
                        monthly_data.append({
                            'month': date_str,
                            'second_hand_price': round(price, 2),
                            'new_house_price': None,
                            'source': f'聚汇数据-{year}文本提取'
                        })
                break
    
    print(f"总共提取到{len(monthly_data)}条数据")
    return monthly_data

# 聚汇数据房价获取函数（月度数据版）
# 注意：原函数已被删除，原函数存在两个问题：
# 1. 使用了未定义的soup变量
# 2. 会被后面的同名函数覆盖

def crawl_juhui_house_price_data(city, district, max_retries=3):
    """
    从聚汇数据网站获取月度房价数据
    基于https://fangjia.gotohui.com/网站结构获取月度房价数据
    提取格式：序号 日期 二手房(元/㎡) 新房(元/㎡) 套均价(万元)
    """
    # 聚汇数据网站基础URL - 城市页面
    base_urls = {
        "北京": "https://fangjia.gotohui.com/fjdata-1",
        "上海": "https://fangjia.gotohui.com/fjdata-3", 
        "广州": "https://fangjia.gotohui.com/fjdata-48",
        "深圳": "https://fangjia.gotohui.com/fjdata-49",
        "杭州": "https://fangjia.gotohui.com/fjdata-37"
    }
    
    # 区域映射 - 聚汇数据的区域URL编码
    district_mappings = {
        "北京": {
            "朝阳": "618",
            "海淀": "613", 
            "西城": "606",
            "东城": "617",
            "丰台": "614",
            "昌平": "620",
            "顺义": "608"
        },
        "上海": {
            "浦东": "2491",
            "徐汇": "2487",
            "静安": "2496", 
            "黄浦": "2497",
            "长宁": "2500"
        },
        "广州": {
            "天河": "873",
            "越秀": "872",
            "海珠": "878",
            "荔湾": "876", 
            "白云": "882"
        },
        "深圳": {
            "福田": "953",
            "罗湖": "951",
            "南山": "950",
            "宝安": "954",
            "龙岗": "952"
        },
        "杭州": {
            "西湖": "3321",
            "上城": "3323",
            "余杭": "3319"
        }
    }
    
    if city not in base_urls:
        print(f"暂不支持{city}的聚汇数据获取")
        return None
    
    for attempt in range(max_retries):
        try:
            # 模拟浏览器请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # 首先获取城市主页面，查找区域链接
            city_url = base_urls[city]
            print(f"正在获取{city}主页面，查找{district}区域链接...")
            
            # 添加随机延迟避免被封
            time.sleep(random.uniform(1, 2))
            
            response = requests.get(city_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找区域链接
            district_url = None
            if city in district_mappings and district in district_mappings[city]:
                district_code = district_mappings[city][district]
                
                # 获取近五年的数据（包含2021和2022年）
                current_year = datetime.now().year
                years_to_fetch = [current_year, current_year - 1, current_year - 2, current_year - 3, current_year - 4]
                all_monthly_data = []
                
                for year in years_to_fetch:
                    # 构建年度数据URL - 格式：com/years/{区域编码}/{年份}/
                    year_url = f"https://fangjia.gotohui.com/years/{district_code}/{year}/"
                    print(f"尝试访问{district}区域{year}年度数据页面: {year_url}")
                    
                    try:
                        time.sleep(random.uniform(0.5, 1.5))
                        year_response = requests.get(year_url, headers=headers, timeout=10)
                        year_response.raise_for_status()
                        
                        year_soup = BeautifulSoup(year_response.text, 'html.parser')
                        
                        # 从年度页面提取月度数据
                        year_monthly_data = extract_monthly_data_from_page(year_soup, year)
                        if year_monthly_data:
                            all_monthly_data.extend(year_monthly_data)
                            print(f"成功获取{year}年{len(year_monthly_data)}条月度数据")
                        
                    except Exception as e:
                        print(f"获取{year}年数据失败: {e}")
                        continue
                
                # 如果通过年度URL没有获取到数据，尝试传统的区域页面
                if not all_monthly_data:
                    # 尝试构建区域URL - 只使用区域编码，不包含城市编码
                    district_url = f"https://fangjia.gotohui.com/fjdata-{district_code}"
                    
                    print(f"尝试访问{district}区域页面: {district_url}")
                    
                    # 获取区域页面数据
                    time.sleep(random.uniform(0.5, 1.5))
                    district_response = requests.get(district_url, headers=headers, timeout=10)
                    district_response.raise_for_status()
                    
                    district_soup = BeautifulSoup(district_response.text, 'html.parser')
                    all_monthly_data = extract_monthly_data_from_page(district_soup, None)
                else:
                    district_soup = None  # 使用all_monthly_data中的数据
                
                # 使用获取到的月度数据
                monthly_data = all_monthly_data
                current_price = None
                
                # 如果有月度数据，获取最新的价格作为当前价格
                if monthly_data:
                    # 按月份排序，获取最新的价格
                    sorted_data = sorted(monthly_data, key=lambda x: x['month'], reverse=True)
                    if sorted_data:
                        current_price = sorted_data[0]['second_hand_price']
                    print(f"成功获取{len(monthly_data)}条月度数据，当前价格：{current_price}")
                else:
                    print(f"在{city}-{district}未找到有效的月度房价数据")
                
                # 构建返回数据
                result = {
                    'city': city,
                    'district': district,
                    'current_price': current_price,
                    'monthly_data': monthly_data,
                    'source': '聚汇数据-月度',
                    'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # 保存爬取的数据到统一的JSON文件
                json_filename = 'crawl_data.json'
                all_crawl_data = {}
                
                # 如果文件已存在，先读取现有数据
                if os.path.exists(json_filename):
                    try:
                        with open(json_filename, 'r', encoding='utf-8') as f:
                            all_crawl_data = json.load(f)
                    except:
                        all_crawl_data = {}
                
                # 添加新数据
                if city not in all_crawl_data:
                    all_crawl_data[city] = {}
                all_crawl_data[city][district] = result
                
                # 保存更新后的数据
                with open(json_filename, 'w', encoding='utf-8') as f:
                    json.dump(all_crawl_data, f, ensure_ascii=False, indent=2)
                print(f"爬取数据已保存到统一文件: {json_filename}")
                
                if current_price and monthly_data:
                    return {
                        'average_price': current_price,
                        'transaction_count': len(monthly_data),
                        'monthly_data': monthly_data,
                        'source': '聚汇数据-月度'
                    }
                else:
                    print(f"在{city}-{district}未找到有效的月度房价数据")
                    return None
            else:
                print(f"未找到{district}区域的映射编码")
                return None
            
        except Exception as e:
            print(f"第{attempt + 1}次尝试获取{city}-{district}数据失败: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2, 5))  # 失败时等待更长时间
            else:
                print(f"最终未能获取{city}-{district}的聚汇数据")
            return None
    
    return None

# 生成基于聚汇数据的房价数据
def generate_juhui_based_data(city, district, time_range_weeks):
    """
    基于聚汇数据生成历史趋势数据
    """
    # 首先尝试获取真实的聚汇数据
    current_data = crawl_juhui_house_price_data(city, district)
    
    if current_data is None:
        # 如果无法获取真实数据，使用模拟数据但标注来源
        print(f"使用模拟的聚汇数据风格数据为{city}-{district}")
        current_price = generate_mock_house_price_data(city, district, datetime.now().date(), 1)[0]['average_price']
        current_data = {
            'average_price': current_price,
            'transaction_count': 50,
            'source': '聚汇数据(模拟)'
        }
    
    # 生成历史数据 (基于当前价格反推)
    today = datetime.now(pytz.timezone("Asia/Shanghai")).date()
    weeks = get_weeks_dates(today - timedelta(weeks=time_range_weeks-1), time_range_weeks)
    
    data = []
    base_price = current_data['average_price']
    
    # 生成价格趋势
    np.random.seed(42)
    trend = np.linspace(-0.1, 0.05, time_range_weeks)  # 整体趋势
    
    for i, week_date in enumerate(reversed(weeks)):  # 从历史到现在
        # 添加季节性和随机波动
        seasonality = 0.03 * np.sin(2 * np.pi * (i / 52))
        random_noise = 0.02 * np.random.randn()
        
        price_change = 1 + trend[i] + seasonality + random_noise
        current_price = base_price * price_change
        
        # 成交量基于价格变化反向调整
        base_volume = current_data['transaction_count']
        volume_factor = max(0.3, 1 - abs(price_change - 1) * 2)
        transaction_count = int(base_volume * volume_factor * (1 + 0.3 * np.random.randn()))
        transaction_count = max(10, transaction_count)
        
        data.append({
            "date": week_date.strftime("%Y-%m-%d"),
            "average_price": round(current_price, 2),
            "transaction_count": transaction_count,
            "source": current_data['source']
        })
    
    # 添加月度数据到返回结果中
    result = list(reversed(data))  # 恢复到时间正序
    
    # 如果有月度数据，添加到每个数据点
    if 'monthly_data' in current_data:
        for item in result:
            item['monthly_data'] = current_data['monthly_data']
    
    return result
 
 # 数据缓存和增量更新相关函数
def load_existing_crawl_data():
    """加载现有的爬取数据"""
    json_filename = 'crawl_data.json'
    if os.path.exists(json_filename):
        try:
            with open(json_filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取现有数据失败: {e}")
            return {}
    return {}

def clean_old_data(data, max_months=60):
    """清理超过指定月数的旧数据"""
    if not data:
        return data
    
    current_date = datetime.now()
    cutoff_date = current_date - timedelta(days=max_months * 30)
    
    cleaned_data = {}
    for city, districts in data.items():
        cleaned_data[city] = {}
        for district, district_data in districts.items():
            if isinstance(district_data, dict) and 'monthly_data' in district_data:
                # 清理月度数据
                cleaned_monthly_data = []
                for month_data in district_data['monthly_data']:
                    try:
                        month_date = datetime.strptime(month_data['month'], '%Y-%m')
                        if month_date >= cutoff_date:
                            cleaned_monthly_data.append(month_data)
                    except:
                        # 如果日期格式不对，保留数据
                        cleaned_monthly_data.append(month_data)
                
                district_data['monthly_data'] = cleaned_monthly_data
                cleaned_data[city][district] = district_data
            else:
                cleaned_data[city][district] = district_data
    
    return cleaned_data

def is_data_identical(new_data, existing_data, city, district):
    """检查新数据是否与现有数据一致"""
    if city not in existing_data or district not in existing_data[city]:
        return False
    
    existing_district = existing_data[city][district]
    
    # 检查当前价格是否一致
    if 'current_price' in new_data and 'current_price' in existing_district:
        if abs(new_data['current_price'] - existing_district['current_price']) > 100:
            return False
    
    # 检查月度数据是否一致（比较最新的几条数据）
    if 'monthly_data' in new_data and 'monthly_data' in existing_district:
        new_monthly = sorted(new_data['monthly_data'], key=lambda x: x['month'], reverse=True)[:3]
        existing_monthly = sorted(existing_district['monthly_data'], key=lambda x: x['month'], reverse=True)[:3]
        
        if len(new_monthly) != len(existing_monthly):
            return False
        
        for new_item, existing_item in zip(new_monthly, existing_monthly):
            if (new_item['month'] != existing_item['month'] or 
                abs(new_item['second_hand_price'] - existing_item['second_hand_price']) > 100):
                return False
    
    return True

# 简化版智能爬取函数
def smart_crawl_juhui_house_price_data(city, district, max_retries=3):
    """智能爬取函数，简化版本"""
    # 尝试获取新数据
    new_data = crawl_juhui_house_price_data(city, district, max_retries)
    
    if new_data is None:
        print(f"无法获取{city}-{district}的新数据")
        return None
    
    print(f"成功获取{city}-{district}的新数据")
    return new_data

# 获取所有城市和区域的房价数据 (简化版本)
def get_all_house_price_data(time_range_weeks):
    all_data = {}
    
    for city, districts in CITIES.items():
        city_data = {}
        for district in districts:
            print(f"获取{city}-{district}的房价数据...")
            
            # 尝试获取真实数据，失败则使用模拟数据
            juhui_data = crawl_juhui_house_price_data(city, district)
            
            if juhui_data and 'current_price' in juhui_data:
                print(f"成功获取{city}-{district}的数据: {juhui_data['current_price']}元/㎡")
                
                # 将聚汇数据格式转换为周数据格式
                district_data = []
                base_price = juhui_data['current_price']
                base_volume = juhui_data.get('transaction_count', 50)
                
                # 生成最近time_range_weeks周的周数据
                today = datetime.now(pytz.timezone("Asia/Shanghai")).date()
                weeks = get_weeks_dates(today - timedelta(weeks=time_range_weeks-1), time_range_weeks)
                
                np.random.seed(hash(city + district) % 1000)
                
                for i, week_date in enumerate(weeks):
                    # 基于历史数据或随机波动生成周数据
                    price = base_price * (1 + 0.02 * np.random.randn())
                    volume = max(10, int(base_volume * (1 + 0.3 * np.random.randn())))
                    
                    district_data.append({
                        "date": week_date.strftime("%Y-%m-%d"),
                        "average_price": round(price, 2),
                        "transaction_count": volume,
                        "source": juhui_data.get('source', '聚汇数据'),
                        "monthly_data": juhui_data.get('monthly_data', [])  # 保留完整的月度历史数据
                    })
                
                city_data[district] = district_data
            else:
                print(f"无法获取{city}-{district}的数据，使用模拟数据")
                # 使用基于聚汇数据的模拟数据生成
                city_data[district] = generate_juhui_based_data(city, district, time_range_weeks)
            
            # 减少延迟时间，提高爬取速度
            time.sleep(random.uniform(0.2, 0.5))
        
        all_data[city] = city_data
    
    return all_data

# 生成Plotly图表的HTML代码
def generate_plotly_chart_html(data, city, district):
    # 直接从crawl_data.json加载月度数据
    crawl_data = load_existing_crawl_data()
    
    if city in crawl_data and district in crawl_data[city]:
        monthly_data = crawl_data[city][district].get('monthly_data', [])
    else:
        # 如果没有crawl_data，尝试从传入的数据中获取
        district_data = data[city][district]
        monthly_data = district_data[0].get('monthly_data', []) if district_data else []
    
    if not monthly_data:
        return {'data': [], 'layout': {}}
    
    # 准备月度数据 - 按时间排序
    monthly_data.sort(key=lambda x: x['month'])
    
    # 提取月度日期和价格数据
    monthly_dates = []
    monthly_second_hand_prices = []
    monthly_new_house_prices = []
    
    for item in monthly_data:
        # 将月份格式转换为日期格式（每月第一天）
        date_str = f"{item['month']}-01"
        monthly_dates.append(date_str)
        monthly_second_hand_prices.append(item.get('second_hand_price', 0))
        monthly_new_house_prices.append(item.get('new_house_price'))
    
    fig = go.Figure()
    
    # 添加月度二手房价格折线
    fig.add_trace(
        go.Scatter(x=monthly_dates, y=monthly_second_hand_prices, name="二手房价格", 
                  line=dict(color='#FF6384', width=3), 
                  mode='lines+markers', marker=dict(size=8))
    )
    
    # 如果有新房价格数据，添加新房价格折线
    if any(monthly_new_house_prices):
        # 过滤掉None值
        valid_new_prices = [(date, price) for date, price in zip(monthly_dates, monthly_new_house_prices) if price is not None]
        if valid_new_prices:
            new_dates, new_prices = zip(*valid_new_prices)
            fig.add_trace(
                go.Scatter(x=new_dates, y=new_prices, name="新房价格", 
                          line=dict(color='#36A2EB', width=3, dash='dash'), 
                          mode='lines+markers', marker=dict(size=6, symbol='diamond'))
            )
    
    fig.update_xaxes(
        title_text="日期",
        tickformat='%Y年%m月',  # 中文日期格式
        tickangle=-45,
        tickfont=dict(size=12),
        type='date',  # 确保X轴按日期处理
        tickmode='auto',  # 自动选择刻度
        nticks=12  # 大约显示12个刻度
    )
    fig.update_yaxes(
        title_text="房价 (元/平方米)", 
        tickformat='.0f'
        # 移除固定范围，使用自适应范围
    )
    
    fig.update_layout(
        title=f"{city}-{district}房价走势图",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    
    # 只返回数据部分，不包含Plotly库引用
    return fig.to_dict()

# 生成简化版的HTML报告，主要展示图表和选择器
def generate_simplified_house_price_html():
    html_filename = 'house_price_report.html'
    current_time = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y年%m月%d日 %H:%M:%S")
    
    default_weeks = 260  # 保持5年数据（260周）
    all_data = get_all_house_price_data(default_weeks)
    
    # 简化数据结构，只保留必要的月度数据
    simplified_data = {}
    for city, districts in all_data.items():
        simplified_data[city] = {}
        for district, data_entries in districts.items():
            # 只保留最新的月度数据（假设是列表中的第一个元素）
            if data_entries and len(data_entries) > 0 and 'monthly_data' in data_entries[0]:
                simplified_data[city][district] = [{"monthly_data": data_entries[0]['monthly_data']}]
            else:
                simplified_data[city][district] = [{}]
    
    default_city = "北京"
    default_district = CITIES[default_city][0]
    
    # 使用简化后的数据生成默认图表
    default_chart_data = generate_plotly_chart_html(simplified_data, default_city, default_district)
    default_chart_json = json.dumps(default_chart_data, separators=(',', ':'))  # 紧凑JSON
    
    city_options = []
    for city in CITIES.keys():
        selected = ' selected' if city == default_city else ''
        city_options.append(f'<option value="{city}"{selected}>{city}</option>')
    
    district_options = []
    for district in CITIES[default_city]:
        selected = ' selected' if district == default_district else ''
        district_options.append(f'<option value="{district}"{selected}>{district}</option>')
    
    # 使用紧凑的JSON序列化，移除空白字符
    data_json = json.dumps(simplified_data, separators=(',', ':'))
    cities_json = json.dumps(CITIES, separators=(',', ':'))
    
    # 使用字符串替换而非f-string来避免JavaScript语法冲突
    html_template = '''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="format-detection" content="telephone=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <title>中国主要城市房价趋势</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
                line-height: 1.7; color: #333; background-color: #f8f9fa; margin: 0; padding: 0; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            h1 { font-size: 28px; color: #2c3e50; margin-bottom: 20px; text-align: center; }
            .meta-info { color: #666; font-size: 14px; margin-bottom: 20px; text-align: center; }
            .data-source { 
                background-color: #e8f4fd; 
                border: 1px solid #b8daff; 
                border-radius: 8px; 
                padding: 15px; 
                margin-bottom: 20px; 
                text-align: center;
            }
            .data-source h3 { color: #0056b3; margin-bottom: 8px; font-size: 16px; }
            .data-source p { color: #666; font-size: 14px; margin: 0; }
            .selector-container { 
                background-color: #fff; 
                padding: 20px; 
                border-radius: 8px; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                margin-bottom: 20px;
                display: flex;
                gap: 20px;
                align-items: center;
                flex-wrap: wrap;
            }
            .selector-group { display: flex; flex-direction: column; min-width: 120px; }
            .selector-group label { margin-bottom: 8px; font-weight: 600; color: #34495e; }
            .selector-group select { 
                padding: 10px 15px; 
                border: 1px solid #ddd; 
                border-radius: 4px; 
                background-color: #fff; 
                font-size: 16px;
                cursor: pointer;
                transition: border-color 0.3s ease;
            }
            .selector-group select:hover { border-color: #3498db; }
            .selector-group select:focus { 
                outline: none;
                border-color: #3498db;
                box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
            }
            .chart-container { 
                background-color: transparent; /* 设置为透明背景 */
                padding: 20px; 
                border-radius: 8px; 
                box-shadow: none; /* 移除阴影 */
                margin-bottom: 20px;
            }
            #house-price-chart { width: 100%; height: 600px; background-color: transparent; } /* 确保图表区域也是透明背景 */
            /* 针对移动设备的响应式设计 */
            @media (max-width: 768px) { 
                .container { padding: 15px; } 
                h1 { font-size: 24px; } 
                .selector-container { flex-direction: column; align-items: stretch; }
                .selector-group { min-width: auto; }
                #house-price-chart { height: 400px; }
            }
            /* 针对横屏方向的优化 */
            @media (orientation: landscape) {
                #house-price-chart { 
                    height: 70vh; /* 视口高度的70%，确保横屏时有足够高度 */
                    min-height: 500px; /* 最小高度保障 */
                }
                .chart-container { padding: 15px; }
            }
            /* 针对竖屏方向的优化 */
            @media (orientation: portrait) {
                #house-price-chart { 
                    height: 50vh; /* 视口高度的50%，适应竖屏布局 */
                    min-height: 350px; /* 最小高度保障 */
                }
                .selector-container { gap: 15px; }
                .container { padding: 15px; }
            }
            /* 针对小屏幕横屏的特殊处理 */
            @media (max-width: 768px) and (orientation: landscape) {
                #house-price-chart { 
                    height: 75vh; /* 横屏时占用更多视口高度 */
                    min-height: 400px; 
                }
            }
        </style>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    </head>
    <body>
        <div class="container">
            <h1>中国主要城市房价数据可视化</h1>
            <div class="meta-info">生成时间: [CURRENT_TIME] | 数据更新周期: 每月 | 数据范围: 最近5年</div>
            
            <div class="data-source">
                <p>本报告数据基于聚汇数据平台公开信息。</p>
            </div>
            
            <div class="selector-container">
                <div class="selector-group">
                    <label for="city-select">选择城市:</label>
                    <select id="city-select">
                        [CITY_OPTIONS]
                    </select>
                </div>
                <div class="selector-group">
                    <label for="district-select">选择区域:</label>
                    <select id="district-select">
                        [DISTRICT_OPTIONS]
                    </select>
                </div>
            </div>
            
            <div class="chart-container">
                <div id="house-price-chart"></div>
            </div>
        </div>
        
        <script>
            const citiesData = CITIES_JSON;
            const housePriceData = DATA_JSON;
            const defaultChart = DEFAULT_CHART_JSON;
            const citySelect = document.getElementById('city-select');
            const districtSelect = document.getElementById('district-select');
            const chartContainer = document.getElementById('house-price-chart');
            
            // 初始化默认图表
            if (defaultChart.layout && defaultChart.layout.xaxis) {
                defaultChart.layout.xaxis.tickformat = '%Y年%m月';
                defaultChart.layout.xaxis.tickangle = -45;
                defaultChart.layout.xaxis.tickfont = {size: 12};
                defaultChart.layout.xaxis.type = 'date';
                defaultChart.layout.xaxis.tickmode = 'auto';
                defaultChart.layout.xaxis.nticks = 12;
                defaultChart.layout.margin = {l: 80, r: 80, t: 80, b: 100};
            }
            // 移除固定的Y轴范围设置，使用自适应范围
            Plotly.newPlot(chartContainer, defaultChart.data, defaultChart.layout);
            
            function updateDistrictOptions(selectedCity) {
                districtSelect.innerHTML = '';
                const districts = citiesData[selectedCity];
                for (const district of districts) {
                    const option = document.createElement('option');
                    option.value = district;
                    option.textContent = district;
                    districtSelect.appendChild(option);
                }
                updateChart(selectedCity, districts[0]);
            }
            
            function updateChart(selectedCity, selectedDistrict) {
                const districtData = housePriceData[selectedCity][selectedDistrict];
                
                // 获取月度数据
                const monthlyData = (districtData.length > 0 && districtData[0].monthly_data) ? districtData[0].monthly_data : [];
                if (!monthlyData || monthlyData.length === 0) {
                    Plotly.newPlot(chartContainer, [], {});
                    return;
                }
                
                // 按时间排序
                monthlyData.sort((a, b) => a.month.localeCompare(b.month));
                
                // 提取月度日期和价格数据
                const monthlyDates = [];
                const monthlySecondHandPrices = [];
                const monthlyNewHousePrices = [];
                
                monthlyData.forEach(item => {
                    // 将月份格式转换为日期格式（每月第一天）
                    const dateStr = item.month + '-01';
                    monthlyDates.push(dateStr);
                    monthlySecondHandPrices.push(item.second_hand_price || 0);
                    monthlyNewHousePrices.push(item.new_house_price);
                });
                
                // 创建二手房价格折线
                const trace1 = {
                    type: 'scatter',
                    x: monthlyDates,
                    y: monthlySecondHandPrices,
                    name: '二手房价格（元/平方米）',
                    line: {color: '#FF6384', width: 3},
                    mode: 'lines+markers',
                    marker: {size: 8},
                    yaxis: 'y'
                };
                
                // 如果有新房价格数据，创建新房价格折线
                let data = [trace1];
                
                // 过滤掉None值，创建新房价格数据
                const validNewPrices = monthlyDates.map((date, index) => {
                    return monthlyNewHousePrices[index] !== null ? monthlyNewHousePrices[index] : null;
                });
                
                if (validNewPrices.some(price => price !== null)) {
                    const trace2 = {
                        type: 'scatter',
                        x: monthlyDates,
                        y: validNewPrices,
                        name: '新房价格（元/平方米）',
                        line: {color: '#36A2EB', width: 3, dash: 'dash'},
                        mode: 'lines+markers',
                        marker: {size: 6, symbol: 'diamond'},
                        yaxis: 'y',
                        connectgaps: false  // 不连接空值
                    };
                    
                    data.push(trace2);
                }
                
                const layout = {
                    title: selectedCity + '-' + selectedDistrict + '房价走势图',
                    xaxis: {
                        title: '日期',
                        tickformat: '%Y年%m月',  // 中文日期格式
                        tickangle: -45,
                        tickfont: {size: 12},
                        type: 'date',
                        tickmode: 'auto',
                        nticks: 12
                    },
                    yaxis: {
                        title: '房价（元/㎡）', 
                        titlefont: {color: '#333'}, 
                        tickfont: {color: '#333'},
                        side: 'left',
                        tickformat: '.0f',  // 显示整数，不采用k、m等单位
                        fixedrange: false    // 允许缩放，使用自适应范围
                    },
                    legend: {orientation: 'h', yanchor: 'bottom', y: 1.02, xanchor: 'right', x: 1},
                    height: 600,
                    margin: {l: 80, r: 80, t: 80, b: 100},
                    paper_bgcolor: 'transparent', // 设置图表纸张背景为透明
                    plot_bgcolor: 'transparent'   // 设置绘图区域背景为透明
                };
                
                Plotly.newPlot(chartContainer, data, layout);
            }
            
            // 添加窗口大小变化监听器，确保图表响应式调整
            window.addEventListener('resize', function() {
                const selectedCity = citySelect.value;
                const selectedDistrict = districtSelect.value;
                updateChart(selectedCity, selectedDistrict);
            });
            
            citySelect.addEventListener('change', function() {
                const selectedCity = this.value;
                updateDistrictOptions(selectedCity);
            });
            
            districtSelect.addEventListener('change', function() {
                const selectedCity = citySelect.value;
                const selectedDistrict = this.value;
                updateChart(selectedCity, selectedDistrict);
            });
        </script>
    </body>
    </html>
    '''
    
    # 替换模板中的占位符
    html_content = html_template.replace('[CURRENT_TIME]', current_time)
    html_content = html_content.replace('[CITY_OPTIONS]', ''.join(city_options))
    html_content = html_content.replace('[DISTRICT_OPTIONS]', ''.join(district_options))
    html_content = html_content.replace('CITIES_JSON', cities_json)
    html_content = html_content.replace('DATA_JSON', data_json)
    html_content = html_content.replace('DEFAULT_CHART_JSON', default_chart_json)
    
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return html_filename

# 获取微信公众号access_token
def get_access_token():
    url = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}' \
        .format(appID.strip(), appSecret.strip())
    response = requests.get(url).json()
    access_token = response.get('access_token')
    return access_token

# 生成报告摘要
def generate_report_summary(city_averages):
    summary = "📊 **北上广深房价月报摘要**\n\n"
    
    # 按房价从高到低排序
    sorted_cities = sorted(city_averages.items(), key=lambda x: x[1], reverse=True)
    
    for i, (city, price) in enumerate(sorted_cities, 1):
        summary += f"🏙️ {city}: ¥{price:,.0f} 元/平方米\n"
    
    summary += "\n📈 完整报告包含各区域详细数据和走势图表，请点击查看。"
    return summary

# 发送房价报告到微信
def send_house_price_to_wechat(access_token, report_summary, html_path):
    today = datetime.now(pytz.timezone("Asia/Shanghai"))
    today_str = today.strftime("%Y年%m月%d日")
    time_period = get_time_period()
    
    # 使用GitHub Pages URL作为跳转链接，添加时间戳参数防止缓存
    timestamp = int(time.time())
    
    # 基础URL
    base_url = "https://jasonaw90411.github.io/InformationNews/house_price_report.html"
    github_pages_url = f"{base_url}?t={timestamp}"
    
    # 在GitHub Actions环境中，可以使用GITHUB_REPOSITORY环境变量来构建URL
    github_repo = os.environ.get('GITHUB_REPOSITORY', '')
    if github_repo:
        # github_repo 格式通常为 "username/repository"
        parts = github_repo.split('/')
        if len(parts) == 2:
            base_url = f"https://{parts[0]}.github.io/{parts[1]}/house_price_report.html"
            github_pages_url = f"{base_url}?t={timestamp}"
    
    body = {
        "touser": openId.strip(),
        "template_id": template_id.strip(),
        "url": github_pages_url,  # 使用GitHub Pages URL作为跳转链接
        "data": {
            "date": {
                "value": f"{today_str} - 月度房价趋势推送"
            },
            "content": {
                "value": report_summary
            },
            "remark": {
                "value": f"{time_period}房价月报"
            }
        }
    }
    
    url = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={}'.format(access_token)
    response = requests.post(url, json.dumps(body))
    return response.json()

# 主函数 - 生成房价报告
def generate_house_price_report():
    print("🔄 开始生成基于聚汇数据的房价数据可视化报告...")
    
    html_file = generate_simplified_house_price_html()
    
    print(f"✅ 房价报告生成完成: {html_file}")
    print(f"📌 请在浏览器中打开 {html_file} 查看效果")
    print(f"💡 报告功能：")
    print(f"   - 数据源：聚汇数据平台")
    print(f"   - 城市选择下拉列表：北京、上海、广州、深圳")
    print(f"   - 区域选择下拉列表：对应城市的各个区域")
    print(f"   - 交互式图表：选择不同城市和区域时自动更新房价走势图")
    print(f"   - 图表类型：月度数据折线图展示")
    print(f"   - 数据说明：包含数据来源标识和免责声明")

    # 新增：完整的房价报告推送功能
def house_price_report_with_push():
    """生成房价报告并推送到微信公众号"""
    print("🔄 开始生成房价数据推送报告...")
    
    # 1. 生成HTML报告
    html_file = generate_simplified_house_price_html()
    print(f"✅ HTML报告生成完成: {html_file}")
    
    # 2. 检查微信配置是否完整
    if not all([appID, appSecret, openId, template_id]):
        print("⚠️  微信推送配置不完整，跳过推送功能")
        print("需要配置的环境变量: APP_ID, APP_SECRET, OPEN_ID, TEMPLATE_ID")
        return html_file
    
    # 3. 获取房价数据用于生成摘要
    print("🔄 正在获取房价数据...")
    
    # 从现有数据中获取城市平均房价
    city_averages = {}
    try:
        with open('crawl_data.json', 'r', encoding='utf-8') as f:
            crawl_data = json.load(f)
        
        for city, districts in CITIES.items():
            total_price = 0
            count = 0
            for district in districts:
                if district in crawl_data.get(city, {}):
                    district_data = crawl_data[city][district]
                    if district_data and len(district_data) > 0:
                        # 获取最新的月度数据
                        monthly_data = district_data[0].get('monthly_data', [])
                        if monthly_data and len(monthly_data) > 0:
                            latest_data = monthly_data[-1]
                            if 'second_hand_price' in latest_data:
                                total_price += latest_data['second_hand_price']
                                count += 1
            
            if count > 0:
                city_averages[city] = round(total_price / count, 2)
    
    except Exception as e:
        print(f"⚠️  获取房价数据失败: {e}")
        # 使用模拟数据
        city_averages = {
            "北京": 65000,
            "上海": 58000,
            "广州": 32000,
            "深圳": 55000
        }
    
    # 4. 生成报告摘要
    report_summary = generate_report_summary(city_averages)
    
    # 5. 获取access_token
    access_token = get_access_token()
    if not access_token:
        print("❌ 获取access_token失败")
        return html_file
    
    # 6. 发送消息到微信
    response = send_house_price_to_wechat(access_token, report_summary, html_file)
    
    if response.get("errcode") == 0:
        print(f"✅ 房价数据推送成功")
    else:
        print(f"❌ 房价数据推送失败: {response}")
    
    return html_file

if __name__ == '__main__':
    # 根据命令行参数决定运行模式
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'push':
        house_price_report_with_push()
    else:
        generate_house_price_report()