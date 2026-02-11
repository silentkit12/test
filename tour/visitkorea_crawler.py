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
        options = webdriver.ChromeOptions()
        
        # 1. 페이지 로드 전략 설정 (안정성을 위해 eager 권장)
        options.page_load_strategy = 'normal' # 혹은 'eager'
        
        if headless:
            options.add_argument('--headless')
        
        # 기본 옵션 설정
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu') # 추가: 그래픽 가속 끔 (충돌 방지)
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 위치 정보/알림 차단
        prefs = {"profile.default_content_setting_values": {"geolocation": 2, "notifications": 2}}
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # [수정] 드라이버는 여기서 한 번만 생성합니다.
        driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(10)
        
        # Wait 객체는 드라이버가 생성된 후에 연결합니다.
        self.wait = WebDriverWait(driver, 15)
        
        return driver
    
    def extract_location_ids(self, url: str = None, max_clicks: int = 1000) -> List[str]:
        if url is None:
            url = f"{self.base_url}/main/area_list.do?type=Place"
            
        print(f"📍 페이지 접속: {url}")
        self.driver.get(url)
        time.sleep(5) 
        
        self._close_popups()
        
        # [추가] 지역 버튼들이 있는 Swiper 영역이 렌더링되도록 살짝 스크롤
        self.driver.execute_script("window.scrollTo(0, 150);")
        time.sleep(2)

        try:
            print("🔍 지역 필터 설정 시작...")

            # ① '서울' 버튼: 텍스트 기반 XPATH가 Swiper 구조에서 가장 강력합니다.
            seoul_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, "//a[.//span[text()='서울']]")))
            
            # 버튼 위치로 스크롤 후 클릭
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", seoul_btn)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", seoul_btn)
            
            print("   - 팝업 로딩 대기 중 (5초)...")
            time.sleep(5) 

            # ③ 체크박스 상태 확인 (input 태그) 및 클릭 (label 태그)
            # mapAll 아이디를 가진 실제 input 요소가 체크되어 있는지 확인합니다.
            checkpoint = self.driver.find_element(By.ID, "mapAll")
            all_chk_label = self.driver.find_element(By.CSS_SELECTOR, "label[for='mapAll']")

            if not checkpoint.is_selected():
                print("   - 현재 미선택 상태이므로 '전체선택' 클릭")
                all_chk_label.click() 
            else:
                print("   - 이미 '전체선택' 상태이므로 클릭 스킵")

            self.driver.execute_script("""
                    var element = document.getElementById('mapAll');
                    var event = new Event('change', { 'bubbles': true });
                    element.dispatchEvent(event);
                """)
            print("   - 변경 이벤트(Change Event) 강제 전송 완료")
            
            time.sleep(2) 

            # ③ '선택' 버튼 클릭 전, 경고창이 이미 떠있다면 닫기
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
                print("   - 미리 뜬 경고창을 닫았습니다.")
            except:
                pass
            
            time.sleep(2) # 클릭 상태 반영 대기            
            
              # '선택' 버튼 찾기
            apply_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[text()='선택']")))
            
            # [중요] 팝업 뒤 페이지가 움직이지 않도록, 스크롤 없이 바로 JS 클릭
            self.driver.execute_script("arguments[0].click();", apply_btn)
            print("✅ '선택' 버튼 클릭 완료")
            
            # 팝업이 닫히고 데이터가 새로고침될 때까지 충분히 대기
            time.sleep(5) 

        except Exception as e:
            print(f"❌ 팝업 처리 중 오류 발생: {e}")


# 1. 페이지 하단으로 스크롤하여 더보기 버튼이 로드되게 함
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # # 페이지 스크롤하여 컨텐츠 로드
        # self.driver.execute_script("window.scrollTo(0, 500);")
        # time.sleep(1)
        
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
        
        # 페이지 소스 파싱
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        
        # 장소 카드에서 ID 추출 (goDetailPage 패턴)
        location_ids = []
        links = soup.find_all('a', href=re.compile(r'goDetailPage\('))
        
        for link in links:
            href = link.get('href', '')
            # goDetailPage('아이디값') 패턴에서 ID 추출
            match = re.search(r"goDetailPage\('([^']+)'\)", href)
            if match:
                location_id = match.group(1)
                if location_id not in location_ids:
                    location_ids.append(location_id)
                    
                    # 장소명도 함께 출력
                    name = link.get_text(strip=True) or "이름 없음"
                    print(f"  ✓ {name} (ID: {location_id})")
        
        print(f"\n✅ 총 {len(location_ids)}개 장소 발견 (더보기 {click_count}회 클릭)\n")
        return location_ids
    
    def _close_popups(self):
        """
        팝업 자동 처리 (위치 정보 동의 등)
        """
        try:
            # 1. 위치 정보 팝업 처리 (동의 버튼 클릭)
            try:
                # 팝업이 나타날 때까지 대기
                location_popup = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.ID, "locationServicePop"))
                )
                
                # '동의' 버튼 찾기 및 클릭
                agree_button = self.driver.find_element(
                    By.XPATH, 
                    "//div[@id='locationServicePop']//a[text()='동의']"
                )
                
                if agree_button.is_displayed():
                    # JavaScript로 클릭 (더 안정적)
                    self.driver.execute_script("arguments[0].click();", agree_button)
                    print("  ✓ 위치 정보 동의 완료")
                    time.sleep(1)
                    return  # 동의 버튼 클릭 성공 시 종료
            except:
                # 위치 정보 팝업이 없으면 다음 단계로
                pass
            
            # 2. 기타 팝업 닫기 (닫기 버튼)
            close_selectors = [
                "//button[contains(text(), '닫기')]",
                "//button[contains(text(), '취소')]",
                "//button[contains(@class, 'close')]",
                "//button[contains(@class, 'btn_close')]",
                "//a[contains(@class, 'close')]",
                "//button[@aria-label='닫기']",
                "//button[@aria-label='Close']",
            ]
            
            for selector in close_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            print("  ✓ 팝업 닫기 완료")
                            time.sleep(0.5)
                            return  # 하나만 닫고 종료
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
    
    def save_location_ids(self, location_ids: List[str], filename: str):
        """장소 ID 목록을 JSON 파일로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(location_ids, f, ensure_ascii=False, indent=2)
        print(f"\n💾 ID 목록 저장 완료: {filename}")
        print(f"   총 {len(location_ids)}개 ID")
    
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
        default=1000,
        help='더보기 버튼 최대 클릭 횟수 (기본값: 1000)'
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
        
        # ID 목록 저장
        crawler.save_location_ids(location_ids, f'{args.output}_ids.json')
        
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
