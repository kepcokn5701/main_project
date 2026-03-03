module.exports = {
  metadata: {
    id: 2,
    sim: 'voc',
    category: '고객서비스',
    title: 'VOC 문의/답변 자동화',
    subtitle: 'LLM 기반 표준답변 추천 시스템',
    problem: '유사 반복 문의 多, 담당자별 답변 품질 편차 크고 과거 사례 검색에 시간 소요.',
    solution: 'RAG 방식으로 과거 답변 DB 구축 후 유사 문의 자동 분류 및 초안 답변 즉시 추천.',
    stack: [
      {n:'Python',t:'lang'},
      {n:'LangChain',t:'lib'},
      {n:'FastAPI',t:'back'},
      {n:'ChromaDB',t:'db'},
      {n:'React',t:'front'},
      {n:'OpenAI API',t:'ai'}
    ],
    ai: [
      {n:'GPT-4o',d:'답변 생성 및 분류',free:false,src:'OpenAI API'},
      {n:'text-embedding-3',d:'문서 임베딩 (RAG)',free:false,src:'OpenAI API'},
      {n:'ChromaDB',d:'벡터 유사도 검색',free:true,src:'오픈소스'}
    ]
  }
};