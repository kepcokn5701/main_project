# main_project

**초보자용 실행 매뉴얼 (프로그래밍 지식 없어도 됩니다!)**

1. **Node.js 설치**
   - [https://nodejs.org](https://nodejs.org) 에서 LTS(권장) 버전을 받아 설치하세요.
   - 설치 완료 후 Powershell을 열고 `node -v` 명령어가 버전을 출력하면 성공입니다.

2. **프로젝트 폴더로 이동**
   ```powershell
   cd C:\Users\Admin\Desktop\project\main_project
   ```
   이는 깃허브에서 받은 소스가 있는 위치입니다.

3. **의존성 설치 (한 번만)**
   ```powershell
   npm install
   cd packages\cs && npm install  # 첫 번째 과제 모듈(샘플)도 설치
   ```
   이 명령은 필요한 라이브러리를 자동으로 내려받습니다.

4. **서버 실행**
   ```powershell
   npm start
   ```
   - 화면에 `Server listening on 3000` 이 보이면 성공입니다.
   - 서버는 계속 실행 중이어야 하므로 창을 닫지 마세요.

5. **웹페이지 열기**
   - 브라우저를 열고 주소창에 `http://localhost:3000` 입력
   - 대시보드가 나타나며, 각 과제 카드의 "시뮬레이션 보기" 버튼을 누르면 실행됩니다.

6. **API 키 입력 (옵션)**
   - 상단에 있는 **"키 설정"** 버튼을 클릭
   - 서비스 이름(EX: openai, huggingface)과 키를 차례대로 입력
   - 특정 과제들이 필요로 하는 경우가 아니라면 OpenAI 키는 **필수 아님**
   - 이후에는 백엔드에서 키를 자동으로 사용합니다.

   > **어디에 입력할까? 보안은?**
   > - 웹 UI 입력은 편리하지만, 키가 서버 메모리에만 저장되어
   >   서버가 재시작되면 사라집니다. 또한 이 방식은 개발/시연 용도이며,
   >   운영 환경에서는 `.env` 파일에 키를 넣고 깃 등에 커밋하지 않는
   >   것이 안전합니다.
   > - `.env` 파일을 루트 또는 각 패키지 폴더에 두고 `OPENAI_API_KEY=...`
   >   처럼 작성하세요. 이 파일은 `.gitignore`에 포함시켜야 합니다.
   > - 민감한 값은 절대 공개 저장소에 올리지 말고, 운영 시에는
   >   환경 변수(예: 호스팅 서비스의 설정 패널)나 비밀 관리 도구를
   >   사용하세요.

7. **종료 방법**
   - 서버 창에서 Ctrl+C 를 눌러 중단
   - 나중에 다시 실행하려면 4번부터 반복하면 됩니다.

---

### ⚠ 포트 충돌 해결
서버를 여러번 실행하거나 비정상 종료 후 `EADDRINUSE` 오류가 나타나면
3000번 포트가 아직 사용 중이기 때문입니다. 해결 방법은:

1. 몇 초 기다려보세요. OS에서 TCP 연결이 닫히면 자동으로 해제됩니다.
2. 터미널에서 아래 명령으로 포트 사용자를 확인 및 종료합니다:
   ```powershell
   netstat -ano | findstr :3000
   taskkill /PID <PID> /F    # PID가 표시되면 종료
   ```
3. 그래도 안된다면 다른 포트로 실행할 수 있습니다:
   ```powershell
   $env:PORT=3001; npm start
   ```
   또는 `set PORT=3001` (PowerShell이 아닌 CMD에서)처럼 환경변수를
   설정하면 `http://localhost:3001`에서 페이지를 볼 수 있습니다.
4. 가장 확실한 방법: 컴퓨터를 재부팅하면 모든 네트워크 포트가 초기화됩니다.

서버 코드는 `process.env.PORT`를 읽으므로 위와 같이 포트를 바꾸면
문제 없이 다른 포트로 동작합니다.

---

## 🧪 HuggingFace LLM 테스트 하기

HuggingFace API 키를 `.env`에 입력한 다음, 아래 주소로 요청을 보내면
간단한 텍스트 생성 응답을 받을 수 있습니다.

```bash
# 프롬프트를 지정하지 않으면 기본 문장으로 테스트합니다
curl "http://localhost:3000/api/test-hf?prompt=테스트+문장"
```

응답이 JSON 형태로 오며, 모델 출력 텍스트가 포함되어 있습니다. 이로써
환경이 제대로 구성되었는지 확인할 수 있습니다.

(키는 `process.env.HUGGINGFACE_API_KEY` 또는 웹 UI에서 설정한 값에서
자동으로 읽어옵니다.)

---

이 저장소는 전력산업 AI 혁신 과제 10개에 대한 인터랙티브 시뮬레이션을 포함한 프로토타입 웹 앱입니다.

## 프로젝트 구조

```
/main_project
├─ packages/                # 각 과제별 모듈(메타데이터 + 서버 로직)
│   ├─ cs/                  # 고객경험관리 예시 패키지
│   │   ├─ index.js         # 메타데이터
│   │   └─ package.json
│   └─ ...                  # 다른 과제들은 같은 구조로 추가
├─ modules/                 # 브라우저에서 불러오는 시뮬레이션 코드
│   └─ cs.js                # CS 시뮬레이션 모듈 (ESM)
├─ frontend/                # 정적 프런트엔드 파일 (같은 index.html 사용)
│   └─ public/index.html
├─ server.js                # Express 서버
└─ package.json             # 루트 패키지 (workspaces 설정)
```

- **모듈화**: `packages/<project>` 폴더에 해당 과제와 연관된 npm 모듈/API 키/백엔드 코드를 넣습니다.
  - 필요한 서드파티 라이브러리는 해당 폴더 `package.json`에 추가하고 `npm install`하면 됩니다.
- **프런트엔드**: 메인 페이지는 동일하지만 시뮬레이션은 `/modules/<sim>.js` ES 모듈을 동적으로 불러옵니다.
  각 과제 폴더에 시뮬레이션 코드를 따로 관리하면 교체/삭제가 쉽습니다.

## 실행 방법

1. Node.js 18+를 설치합니다.
2. 루트에서 종속성 설치:
   ```bash
   cd c:\Users\Admin\Desktop\project\main_project
   npm install
   cd packages/cs && npm install      # 필요한 경우 개별 패키지에서 설치
   ```
3. 서버 시작:
   ```bash
   npm start
   ```
4. 브라우저에서 `http://localhost:3000`으로 접속하면 데모 페이지가 열립니다.

## API 키 및 사용자 데이터 입력

- 환경 변수를 사용하거나, 웹 UI를 통해 키를 설정할 수 있습니다.
- `.env` 파일을 루트 또는 각 패키지 폴더에 두고 다음과 같이 작성하세요:
  ```dotenv
  OPENAI_API_KEY=sk-...
  HUGGINGFACE_API_KEY=hf_...
  // 패키지별 키는 패키지 폴더에서도 개별 .env 사용 가능
  ```
- 런타임 중에 `/api/keys` 엔드포인트에 `POST {service, key}` 요청을 보내면 메모리에 저장됩니다.
  예:
  ```js
  fetch('/api/keys', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({service:'openai',key:'sk-...'})});
  ```
- 각 패키지의 서버 로직에서 `process.env` 또는 `userKeys` 객체를 읽어 사용하세요.

## 새로운 프로젝트 추가

1. `packages/<identifier>` 폴더를 생성하고 `package.json`과 `index.js`를 작성합니다.
2. `modules/<identifier>.js`에 시뮬레이션 코드를 구현하고 `export function start(el){}` 형태로 내보냅니다.
3. `packages/<identifier>/index.js`의 `metadata` 객체에 `id`, `sim`, `title` 등 필요한 정보를 포함하세요.
4. 필요 시 서버 `/api/projects` 로직을 확장하거나, 각 패키지에서 자체 라우터를 추가할 수 있습니다.

## 확장 아이디어

- 시뮬레이션 코드를 실제 API 호출로 교체하여 "진짜 서비스"로 전환
- 각 패키지에 독립적인 Express/Next.js 서버를 두고 루트 서버가 프록시 역할 수행
- Docker/CI 배포 스크립트 작성

---

모듈 단위로 분리했기 때문에 결과물이 예상과 다를 때 해당 폴더만 지우거나 교체하면 됩니다. 필요하다면 `frontend/public/index.html`을 React/Next.js로 재작성하고 동일한 API를 호출하게 하면 됩니다. Have fun!