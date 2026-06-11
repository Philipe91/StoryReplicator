# Relatório de Validação — StoryReplicator v4.0

Bateria de 10 vídeos em 4 categorias. Pipeline determinístico completo
(hook, retention, narration director, inteligência visual, música, sound design,
quality report v2) executado por caso. Geração de IA (roteiro) feita manualmente
como roteirista, dado que o sistema roda sem API paga.

## Resultados por vídeo

| # | Caso | Categoria | hook | retention | visual | vis.qual | CTR | vídeos | imgs | reuso |
|---|------|-----------|------|-----------|--------|----------|-----|--------|------|-------|
| 1 | Ponzi | Golpe | 6.4 | 90 | 10.0 | 8.8 | bom 5-8% | 0 | 6 | 5 |
| 2 | Abagnale | Golpe | 6.4 | 70 | 5.0 | 0.0 | médio 3-5% | 0 | 0 | 0 |
| 3 | Mike galinha | Inacreditável | 6.4 | 90 | 10.0 | 9.1 | bom | 0 | 6 | 5 |
| 4 | Roy Sullivan | Inacreditável | 6.4 | 90 | 10.0 | 7.5 | bom | 0 | 6 | 3 |
| 5 | Alcatraz | Inacreditável | 6.4 | 90 | 10.0 | 8.2 | bom | 0 | 6 | 2 |
| 6 | Dyatlov | Mistério | 6.4 | 90 | 10.0 | 8.8 | bom | 0 | 6 | 5 |
| 7 | Mary Celeste | Mistério | 6.4 | 90 | 5.0 | 0.0 | bom | 0 | 0 | 0 |
| 8 | Amelia Earhart | Mistério | 6.4 | 90 | 5.0 | 0.0 | bom | 0 | 0 | 0 |
| 9 | Hindenburg | Acidente | 6.4 | 90 | 10.0 | 8.6 | bom | 2 | 4 | 2 |
| 10 | Titanic | Acidente | 6.4 | 90 | 10.0 | 9.2 | bom | 0 | 6 | 5 |

**Médias:** hook 6.4 · retention 88 · visual 8.5 · vis.qual 6.0 · CTR "bom (5-8%)"
**Totais:** 40 imagens reais · 2 vídeos reais · 27/60 cenas reusadas (45%) · 3 casos com 0 imagens

---

## 1. O que ainda parece artificial

- **Hooks idênticos e genéricos.** Os 10 vídeos receberam o MESMO score de hook (6.4)
  e quase sempre a mesma fórmula ("Como X enganou o mundo inteiro?"). O hook_engine
  por template não diferencia caso a caso — soa repetitivo e artificial.
- **Voz TTS.** Mesmo com pitch/rate e pausas do narration_director, a entonação é
  uniforme; falta a variação emocional de um locutor humano nos clímax.
- **Pausas heurísticas.** O narration_director insere "..." por regra de pontuação,
  não por compreensão do sentido — às vezes a pausa cai em lugar levemente artificial.
- **Reuso de imagem.** 45% das cenas repetem a mesma imagem de outra cena (reuso),
  o que cria sensação de "loop" e revela que não houve material único suficiente.

## 2. O que reduz a retenção

- **Hook fraco e uniforme (6.4/10).** É o fator nº 1 de retenção e o mais fraco do
  sistema. Sem um hook forte e específico, o espectador abandona nos 3s iniciais.
- **Cobertura visual repetitiva.** Onde há muito reuso (Ponzi, Mike, Dyatlov, Titanic
  com 5/6 cenas reusadas), o olho percebe a repetição e a retenção cai.
- **Baixíssima presença de vídeo** (2 em 60 cenas). Imagem estática com Ken Burns
  retém menos que movimento real — documentários profissionais alternam muito vídeo.
- **Abagnale: retention 70** (mais baixo) — coincide com 0 imagens e roteiro mais
  expositivo; confirma que cobertura fraca + exposição derrubam a retenção.

## 3. Cenas / casos com cobertura visual fraca

- **ZERO imagens (3 casos):** Abagnale, Mary Celeste, Amelia Earhart.
  - Earhart e Mary Celeste **têm material** (6 candidatos válidos cada quando testados
    isoladamente) — zeraram por **rate-limit do Wikimedia em lote** (ver gargalo nº 1).
  - Abagnale é falha real de query: "abagnale 1960s airport pilot" → 0 resultados
    (pessoa recente, pouco domínio público + descrição genérica).
- **FRACA (6 casos):** Ponzi, Mike, Sullivan, Dyatlov, Titanic e Hindenburg tiveram de
  1 a 4 imagens únicas e o resto reusado. Cenas de conceito abstrato ("tamanho",
  "milhões por semana", "probabilidade") não têm imagem óbvia e caem no reuso.
- **FORTE (1 caso):** apenas Alcatraz (4/6 próprias, 2 reuso).

## 4. Módulos que entregam mais valor

1. **Âncora de assunto + queries curtas (visual engine).** Quando a rede coopera,
   garante precisão real (Hindenburg, Titanic, Alcatraz com imagens 100% do caso).
   É o maior salto de qualidade vs. versões anteriores (fim do "burro aleatório").
2. **Retention Engine.** Discrimina de fato: detectou tensão 6.7 vs 10 e o caso fraco
   (Abagnale 70). Dá diagnóstico acionável antes de renderizar.
3. **Narration Director.** As pausas dramáticas nos clímax melhoram perceptivelmente
   a narração mesmo sem locutor humano.
4. **Visual Quality Filter.** Onde baixou, manteve resolução alta (vis.qual 8-9.2).
5. **Sound Design + Music (validados à parte).** Funcionam end-to-end e dão imersão.

## 5. Principais gargalos restantes

1. **🔴 Rate-limit do Wikimedia em lote (gargalo nº 1).** Rodando 1 caso isolado →
   8-9 imagens únicas. Rodando 10 casos em rajada → 1-4 por caso, e 3 casos zeram.
   Centenas de requests seguidas são limitadas. **Impacto: cobertura cai ~70% em escala.**
   Solução: throttling global, retry com backoff, paralelismo controlado, mais provedores.
2. **🟠 Hook Engine pouco discriminante.** Score fixo 6.4, fórmula repetida. Precisa de
   geração mais variada e específica por caso (é o fator nº 1 de retenção).
3. **🟠 Baixa taxa de vídeo real** (2/60). Fontes gratuitas têm pouco footage; sem
   Pexels/Pixabay (chave grátis) o mix fica quase só imagem.
4. **🟡 Reuso de imagem alto (45%).** Conceitos abstratos não têm imagem; faltam
   queries de B-roll genérico para preencher com variedade (não com repetição).
5. **🟡 Queries fracas para pessoas recentes / conceitos** (Abagnale). Descrições
   genéricas ("1960s airport") trazem zero; falta fallback de B-roll de época.

---

## Veredito

O **núcleo está sólido**: quando a rede coopera, a precisão visual e a estrutura
narrativa entregam vídeos coerentes (Hindenburg, Titanic, Alcatraz). Os **3 maiores
limitadores de qualidade** hoje são, em ordem: (1) rate-limit em escala derrubando a
cobertura, (2) hook genérico reduzindo retenção, (3) escassez de vídeo real. Nenhum é
de arquitetura — são de **robustez de aquisição e variedade**, endereçáveis sem
refatoração. Recomendação: antes de qualquer feature nova, atacar o gargalo nº 1
(throttling/retry/mais fontes) e o nº 2 (hook por caso).
