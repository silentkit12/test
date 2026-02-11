"""
한국관광공사 구석구석 웹사이트 크롤러
- 메인 페이지에서 장소 카드 목록 수집
- 각 장소의 상세 정보 크롤링
"""

import re
import time
import json
import argparse
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import pandas as pd


class VisitKoreaCrawler:
    """한국관광공사 구석구석 크롤러"""
    
    def __init__(self, headless: bool = False):
        """
        Args:
            headless: 브라우저를 백그라운드에서 실행할지 여부
        """
        self.base_url = "https://korean.visitkorea.or.kr"
        self.driver = self._init_driver(headless)
        
    def _init_driver(self, headless: bool = False):
        """
        Chrome WebDriver 초기화
        
        Args:
            headless: 헤드리스 모드 여부
            
        Returns:
            WebDriver 인스턴스
        """
        options = webdriver.ChromeOptions()
        
        if headless:
            options.add_argument('--headless')
        
        # 기본 옵션
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 위치 정보, 알림 등 권한 차단
        prefs = {
            "profile.default_content_setting_values": {
                "geolocation": 2,  # 위치 정보 차단 (1: 허용, 2: 차단)
                "notifications": 2,  # 알림 차단
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        # 자동화 감지 방지
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        
        return driver
    
    def extract_location_ids(self, url: str = None, max_clicks: int = 100):
        if url is None:
            url = f"{self.base_url}/main/area_list.do?type=Place"
            
        print(f"📍 페이지 접속: {url}")
        self.driver.get(url)
        
        # 1. 초기 로딩 대기 (리스트의 첫 번째 요소가 보일 때까지)
        wait = WebDriverWait(self.driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.list_thum_type.type1 li")))
        except:
            print("⚠️ 페이지 로딩이 너무 오래 걸립니다.")
        
        # 위치 정보 팝업 자동 닫기
        self._close_popups()
        time.sleep(2)  # 팝업 닫은 후 대기
        
        # 페이지 스크롤하여 컨텐츠 로드
        self.driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)
        
        # 더보기 버튼을 계속 클릭하여 모든 카드 로드
        click_count = 0
        while click_count < max_clicks:
            try:
                # 더보기 버튼 찾기
                more_button = None
                
                # 여러 선택자 시도
                selectors = [
                    "//button[contains(text(), '더보기')]",
                    "//button[contains(@class, 'btn_more')]",
                    "//a[contains(text(), '더보기')]",
                    "//a[contains(@class, 'more')]"
                ]
                
                for selector in selectors:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            more_button = btn
                            break
                    if more_button:
                        break
                
                if not more_button:
                    print(f"  ℹ️  더보기 버튼을 찾을 수 없습니다. (총 {click_count}회 클릭)")
                    break
                
                # JavaScript로 버튼 클릭 (element click intercepted 방지)
                try:
                    self.driver.execute_script("arguments[0].click();", more_button)
                    click_count += 1
                    print(f"  🔄 더보기 클릭 {click_count}회")
                    time.sleep(2)  # 로딩 대기
                except Exception as e:
                    print(f"  ⚠️  클릭 실패, 재시도: {str(e)[:30]}")
                    # 스크롤 후 재시도
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_button)
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", more_button)
                    click_count += 1
                    print(f"  🔄 더보기 클릭 {click_count}회 (재시도 성공)")
                    time.sleep(2)
                
            except Exception as e:
                print(f"  ℹ️  더보기 버튼 클릭 종료: {str(e)[:50]}")
                break
        print("⏳ 데이터 파싱 준비 중...")
        time.sleep(3)

        # 페이지 소스 파싱
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        location_ids = []
        # 1. id가 contentList인 ul 안의 모든 li를 찾습니다.
        items = soup.select("#contentList > li")

        for item in items:
            try:
                # 2. li 안에 있는 a 태그를 찾습니다.
                anchor = item.find('a')
                if not anchor:
                    continue
                    
                href_value = anchor.get('href', '')
                
                # 3. 정규표현식으로 coid= 뒤의 ID 값을 추출합니다.
                # [0-9a-f-] 패턴은 숫자, 소문자, 하이픈이 섞인 UUID를 의미합니다.
                match = re.search(r"coid=([0-9a-f-]{36})", href_value)
                
                if match:
                    location_id = match.group(1)
                    if location_id not in location_ids:
                        location_ids.append(location_id)
                        
                        # 4. 장소명 추출 (strong 태그)
                        name_tag = anchor.find('strong')
                        name = name_tag.get_text(strip=True) if name_tag else "이름 없음"
                        
                        print(f"  ✓ {name} (ID: {location_id})")
                else:
                    # 혹시 coid가 없고 goDetailPage만 있을 경우를 대비한 2차 시도
                    match_alt = re.search(r"goDetailPage\('([0-9a-f-]{36})'\)", href_value)
                    if match_alt:
                        location_id = match_alt.group(1)
                        if location_id not in location_ids:
                            location_ids.append(location_id)
                            print(f"  ✓ {name} (ID: {location_id} - secondary match)")

            except Exception as e:
                print(f"  ⚠️ 개별 요소 추출 중 오류: {e}")
                continue

            return location_ids
    
    def _close_popups(self):
        """
        팝업 자동 닫기 (위치 정보 동의 등)
        """
        try:
            # 여러 가능한 팝업 닫기 버튼 선택자
            close_selectors = [
                "//button[contains(text(), '닫기')]",
                "//button[contains(text(), '취소')]",
                "//button[contains(@class, 'close')]",
                "//a[contains(@class, 'close')]",
                "//button[@aria-label='닫기']",
                "//button[@aria-label='Close']",
            ]
            
            for selector in close_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            print("  ✓ 팝업 닫기 완료")
                            time.sleep(0.5)
                except:
                    continue
        except Exception as e:
            # 팝업이 없으면 무시
            pass
    
    def crawl_detail_info(self, location_id: str) -> Dict:
        """
        특정 장소의 상세 정보 크롤링
        
        Args:
            location_id: 장소 ID (cotid)
            
        Returns:
            상세 정보 딕셔너리
        """
        detail_url = f"{self.base_url}/detail/ms_detail.do?cotid={location_id}"
        print(f"📄 상세 페이지 접속: {location_id}")
        
        try:
            self.driver.get(detail_url)
            time.sleep(2)
            
            # 기본 정보 수집
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # 장소명
            title_tag = soup.find('h2') or soup.find('h1', class_=re.compile(r'tit'))
            title = title_tag.text.strip() if title_tag else "제목 없음"
            
            # '상세정보' 탭 클릭 (JavaScript로 직접 실행)
            try:
                self.driver.execute_script("tabChange('detailGo');")
                time.sleep(2)  # 탭 전환 대기
                print("  ✓ 상세정보 탭 클릭 완료")
            except Exception as e:
                print(f"  ⚠️  상세정보 탭 클릭 실패: {str(e)}")
            
            # 상세정보 파싱
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            detail_info = self._parse_detail_section(soup)
            
            # 사진 URL 추출
            photo_urls = self._extract_photo_urls(soup)
            
            # 결과 구성
            result = {
                'id': location_id,
                'name': title,
                'url': detail_url,
                'photo_urls': photo_urls,
                **detail_info
            }
            
            print(f"  ✓ {title} - {len(detail_info)}개 항목, {len(photo_urls)}개 사진 수집")
            return result
            
        except Exception as e:
            print(f"  ❌ 오류 발생: {str(e)}")
            return {
                'id': location_id,
                'name': '오류',
                'url': detail_url,
                'error': str(e)
            }
    
    def _parse_detail_section(self, soup: BeautifulSoup) -> Dict:
        """
        상세정보 섹션 파싱
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            상세정보 딕셔너리
        """
        detail_info = {}
        
        # <li> 태그로 구성된 정보 항목 찾기
        list_items = soup.find_all('li')
        
        for item in list_items:
            # 항목명 (Label)
            label_tag = item.find('strong')
            if not label_tag:
                continue
                
            label = label_tag.text.strip()
            
            # 항목값 (Value) - span 태그에서 추출
            value_tags = item.find_all('span', class_='pc') or item.find_all('span')
            
            if value_tags:
                # 여러 span이 있을 경우 합치기
                values = [tag.text.strip() for tag in value_tags if tag.text.strip()]
                value = ' / '.join(values) if values else ''
            else:
                # span이 없으면 전체 텍스트에서 label 제거
                value = item.text.replace(label, '').strip()
            
            if value:
                detail_info[label] = value
        
        return detail_info
    
    def _extract_photo_urls(self, soup: BeautifulSoup) -> List[str]:
        """
        사진 URL 추출
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            사진 URL 리스트
        """
        photo_urls = []
        
        # 사진보기 영역 (id="galleryGo")에서 swiper 슬라이드 찾기
        gallery_section = soup.find('div', id='galleryGo')
        if not gallery_section or not hasattr(gallery_section, 'find_all'):
            return photo_urls
        
        # swiper-slide 내의 모든 img 태그 찾기
        slides = gallery_section.find_all('div', class_='swiper-slide')
        
        for slide in slides:
            img_tag = slide.find('img')
            if img_tag:
                # src 또는 data-src 속성에서 URL 추출
                img_url = img_tag.get('src') or img_tag.get('data-src')
                if img_url and img_url.startswith('http'):
                    # URL에서 &amp; 를 & 로 변환
                    img_url = img_url.replace('&amp;', '&')
                    if img_url not in photo_urls:
                        photo_urls.append(img_url)
        
        return photo_urls
    
    def crawl_multiple(self, location_ids: List[str], delay: float = 1.0) -> List[Dict]:
        """
        여러 장소의 상세 정보 크롤링
        
        Args:
            location_ids: 장소 ID 리스트
            delay: 각 요청 사이 대기 시간 (초)
            
        Returns:
            상세 정보 리스트
        """
        results = []
        total = len(location_ids)
        
        for idx, location_id in enumerate(location_ids, 1):
            print(f"\n[{idx}/{total}] ", end='')
            result = self.crawl_detail_info(location_id)
            results.append(result)
            
            if idx < total:
                time.sleep(delay)
        
        return results
    
    def save_to_csv(self, data: List[Dict], filename: str):
        """결과를 CSV 파일로 저장"""
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n💾 저장 완료: {filename}")
        print(f"   총 {len(data)}개 항목")
    
    def save_to_json(self, data: List[Dict], filename: str):
        """결과를 JSON 파일로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 저장 완료: {filename}")
        print(f"   총 {len(data)}개 항목")
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            print("\n🔚 브라우저 종료")


def main():
    """
    메인 실행 함수
    """
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(
        description='한국관광공사 구석구석 웹사이트 크롤러',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
사용 예시:
  # 10개 장소 크롤링
  python visitkorea_crawler.py --count 10
  
  # 50개 장소 크롤링, 더보기 30회 클릭
  python visitkorea_crawler.py --count 50 --max-clicks 30
  
  # 백그라운드 모드로 100개 크롤링
  python visitkorea_crawler.py --count 100 --headless
        '''
    )
    
    parser.add_argument(
        '--count', '-c',
        type=int,
        default=10,
        help='크롤링할 장소 개수 (기본값: 10)'
    )
    
    parser.add_argument(
        '--max-clicks', '-m',
        type=int,
        default=50,
        help='더보기 버튼 최대 클릭 횟수 (기본값: 50)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='헤드리스 모드로 실행 (브라우저 창 숨김)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='visitkorea_data',
        help='출력 파일명 (확장자 제외, 기본값: visitkorea_data)'
    )
    
    args = parser.parse_args()
    
    # 크롤러 초기화
    crawler = VisitKoreaCrawler(headless=args.headless)
    
    try:
        # 1. 장소 ID 수집 (더보기 버튼 클릭)
        print("=" * 60)
        print("1단계: 장소 ID 수집")
        print("=" * 60)
        location_ids = crawler.extract_location_ids(max_clicks=args.max_clicks)
        
        # 지정된 개수만큼 크롤링
        target_count = min(args.count, len(location_ids))
        target_ids = location_ids[:target_count]
        print(f"\n📊 총 {len(location_ids)}개 중 {target_count}개 장소를 크롤링합니다.\n")
        
        # 2. 상세 정보 크롤링
        print("=" * 60)
        print("2단계: 상세 정보 크롤링")
        print("=" * 60)
        results = crawler.crawl_multiple(target_ids, delay=1.5)
        
        # 3. 결과 저장
        print("\n" + "=" * 60)
        print("3단계: 결과 저장")
        print("=" * 60)
        crawler.save_to_json(results, f'{args.output}.json')
        crawler.save_to_csv(results, f'{args.output}.csv')
        
        print(f"\n✅ 크롤링 완료! {len(results)}개 장소 정보 저장됨")
        
        print("\n" + "=" * 60)
        print("결과 미리보기")
        print("=" * 60)
        for item in results[:2]:
            print(f"\n📍 {item.get('name', '이름 없음')}")
            for key, value in item.items():
                if key not in ['id', 'name', 'url']:
                    print(f"   {key}: {value}")
        
    finally:
        crawler.close()


if __name__ == "__main__":
    main()