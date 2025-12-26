#!/usr/bin/env python3
"""
防盗链绕过测试脚本

用于验证修复是否成功
"""
import time
import requests


def test_without_referer(zip_url: str, proxy_url: str = None) -> bool:
    """测试不带Referer的请求（预期失败）"""
    print("\n" + "=" * 60)
    print("🧪 测试1: 不带Referer（预期: 403 Forbidden）")
    print("=" * 60)
    
    session = requests.Session()
    
    if proxy_url:
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    try:
        response = session.head(zip_url, headers=headers, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ 预期结果：被防盗链拦截")
            tengine_error = response.headers.get('X-Tengine-Error', '')
            if tengine_error:
                print(f"   X-Tengine-Error: {tengine_error}")
            return True
        else:
            print(f"⚠️ 意外结果：状态码 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False
    finally:
        session.close()


def test_with_referer(zip_url: str, referer_url: str, proxy_url: str = None) -> bool:
    """测试带Referer的请求（预期成功）"""
    print("\n" + "=" * 60)
    print("🧪 测试2: 带正确Referer（预期: 200 OK）")
    print("=" * 60)
    
    session = requests.Session()
    
    if proxy_url:
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    
    # Step 1: 先访问下载页面（建立session）
    print(f"📄 Step 1: 访问下载页面...")
    print(f"   URL: {referer_url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        response = session.get(referer_url, headers=headers, timeout=10)
        print(f"   状态码: {response.status_code}")
        print(f"   Cookies: {list(session.cookies.keys())}")
    except Exception as e:
        print(f"   ⚠️ 访问失败（可能不影响结果）: {e}")
    
    # 等待
    time.sleep(1)
    
    # Step 2: 带Referer请求ZIP
    print(f"\n📥 Step 2: 请求ZIP文件...")
    print(f"   URL: {zip_url}")
    print(f"   Referer: {referer_url}")
    
    download_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': referer_url,
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document',
    }
    
    try:
        response = session.head(zip_url, headers=download_headers, timeout=10)
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 成功绕过防盗链！")
            content_length = response.headers.get('Content-Length', 'unknown')
            content_type = response.headers.get('Content-Type', 'unknown')
            print(f"   Content-Type: {content_type}")
            print(f"   Content-Length: {content_length} bytes")
            return True
        elif response.status_code == 403:
            print("❌ 仍然被拦截")
            tengine_error = response.headers.get('X-Tengine-Error', '')
            if tengine_error:
                print(f"   X-Tengine-Error: {tengine_error}")
            return False
        else:
            print(f"⚠️ 意外状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False
    finally:
        session.close()


def test_with_wrong_referer(zip_url: str, proxy_url: str = None) -> bool:
    """测试错误的Referer（预期失败）"""
    print("\n" + "=" * 60)
    print("🧪 测试3: 带错误Referer（预期: 403 Forbidden）")
    print("=" * 60)
    
    session = requests.Session()
    
    if proxy_url:
        session.proxies = {'http': proxy_url, 'https': proxy_url}
    
    # 使用错误的Referer（不在白名单内）
    wrong_referer = "https://example.com/page/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': wrong_referer,
    }
    
    print(f"   URL: {zip_url}")
    print(f"   Referer: {wrong_referer}")
    
    try:
        response = session.head(zip_url, headers=headers, timeout=10)
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ 预期结果：错误的Referer被拦截")
            return True
        else:
            print(f"⚠️ 意外结果：状态码 {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False
    finally:
        session.close()


def main():
    """运行所有测试"""
    print("=" * 60)
    print("🔧 Tengine CDN 防盗链绕过测试")
    print("=" * 60)
    
    # 测试配置 - 请根据实际情况修改
    zip_url = "https://ipo.ai-tag.cn/2025/04/202504291200327477262.zip"
    referer_url = "https://ipoipo.cn/xiazai/123456/"  # 替换为实际的下载页面URL
    
    # 代理配置（如果使用）
    # proxy_url = "http://127.0.0.1:7890"
    proxy_url = None  # 不使用代理时设为 None
    
    print(f"\n📋 测试配置:")
    print(f"   ZIP URL: {zip_url}")
    print(f"   Referer: {referer_url}")
    print(f"   代理: {proxy_url or '不使用'}")
    
    results = []
    
    # 测试1: 不带Referer
    results.append(("不带Referer", test_without_referer(zip_url, proxy_url)))
    
    # 测试2: 带正确Referer
    results.append(("带正确Referer", test_with_referer(zip_url, referer_url, proxy_url)))
    
    # 测试3: 带错误Referer
    results.append(("带错误Referer", test_with_wrong_referer(zip_url, proxy_url)))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！防盗链绕过方案有效。")
    else:
        print("⚠️ 部分测试未通过，请检查配置。")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    main()