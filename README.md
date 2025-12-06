# Marathon Registration Monitor (Runnable Fighter)

이 스크립트는 **러너블(Runable)** 사이트의 특정 마라톤 대회 페이지를 모니터링하다가, **신청 불가능했던 종목(10K, Half, 5K 등)**이 신청 가능(취소표 발생 등)해지면 **Slack으로 알림**을 보내주는 도구입니다.

## 기능
- 30초 간격으로 지정된 상품 페이지 모니터링
- "종목" 드롭다운을 자동으로 열어 실제 선택 가능 여부 확인
- **10K, Half, Full, 5K** 중 하나라도 선택 가능하면 즉시 Slack 알림 전송
- 모든 항목이 매진 상태여도, 1시간 간격으로 "모니터링 정상 작동 중" Heartbeat 알림 전송

## 사전 요구 사항
- Python 3.8 이상
- Google Chrome 또는 Chromium 브라우저

## 설치 방법

1. **저장소 클론 (다운로드)**
   ```bash
   git clone https://github.com/loje0611/runnable-fighter.git
   cd runnable-fighter
   ```

2. **의존성 라이브러리 설치**
   아래 명령어로 필요한 파이썬 패키지를 설치합니다.
   ```bash
   pip install playwright
   playwright install chromium
   ```

## 설정 (Configuration)

이 스크립트를 실행하기 전에 두 가지 설정 파일(`config.json`, `cookies.json`)을 생성해야 합니다.

### 1. `config.json` 생성
모니터링할 **대회 URL**과 알림을 받을 **Slack Webhook URL**을 설정합니다.
제공된 `config.sample.json` 파일을 복사하여 `config.json`을 만들고 내용을 수정하세요.

```bash
cp config.sample.json config.json
vi config.json
```

```json
{
    "target_url": "https://runable.me/product/3299?comp=2955",
    "slack_webhook_url": "YOUR_SLACK_WEBHOOK_URL_HERE"
}
```
> **Slack Webhook URL 얻는 법**: [Slack API](https://api.slack.com/apps) -> Create New App -> Incoming Webhooks On -> Add New Webhook -> URL 복사

### 2. `cookies.json` 생성 (로그인 세션)
러너블 사이트는 로그인이 필요할 수 있습니다. 브라우저에서 로그인한 후 **쿠키(Cookie)** 정보를 `cookies.json` 파일로 저장해야 합니다.
(EditThisCookie 같은 크롬 확장프로그램을 사용하여 JSON으로 추출하거나, 개발자 도구 등을 사용하세요.)

`cookies.json` 형식 예시:
```json
[
  {
    "domain": "runable.me",
    "name": "access_token",
    "value": "...",
    ...
  }
]
```
> **주의**: 이 파일에는 개인 로그인 정보가 포함되므로 절대 Github 등에 업로드하지 마세요. (`.gitignore`에 의해 자동 제외됨)

## 실행 방법

설정이 완료되면 아래 명령어로 모니터링을 시작합니다.

```bash
./run_monitor.sh
```
또는
```bash
python3 monitor_runner.py
```

## 작동 방식
- 실행하면 브라우저가 열리고(기본: Headless=False, 화면 보임) 대상 페이지로 이동합니다.
- "대회 신청 하기" 버튼을 누르고 "종목" 드롭다운을 엽니다.
- 항목을 클릭해보며 실제 신청 가능한지 테스트합니다.
- **신청 가능 시**: 로그 출력 및 Slack 알림 전송 (이후 1분 대기)
- **신청 불가 시**: 30초 대기 후 재시도 (1시간마다 Heartbeat 알림)

---
**Note**: 이 스크립트는 학습 및 개인적인 편의를 위해 작성되었습니다. 사이트의 구조 변경에 따라 작동하지 않을 수 있습니다.
