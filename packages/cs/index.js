// metadata for CS project, used by backend API
module.exports = {
  metadata: {
    id: 1,
    sim: 'cs',
    category: '고객서비스',
    title: '고객경험관리(CS) 분석',
    subtitle: 'AI 기반 설문 자동 분석 시스템',
    problem: '월 5만 건+ 설문 데이터 수작업 분석. 과도한 시간 소요로 CS 활동에 미활용됨.',
    solution: '형태소 분석+ML로 감성 분류, 워드클라우드, 잠재 민원 고객 사전 케어 리스트 자동 생성.',
    stack: [
      {n:'Python 3.11',t:'lang'},
      {n:'Pandas',t:'lib'},
      {n:'KoNLPy',t:'ai'},
      {n:'Streamlit',t:'front'},
      {n:'FastAPI',t:'back'},
      {n:'scikit-learn',t:'ai'}
    ],
    ai: [
      {n:'KoELECTRA',d:'한국어 감성 분류',free:true,src:'HuggingFace'},
      {n:'GPT-4o',d:'인사이트 자동 요약',free:false,src:'OpenAI API'},
      {n:'LDA',d:'토픽 모델링',free:true,src:'scikit-learn'}
    ]
    // ... add other fields as needed
  }
};