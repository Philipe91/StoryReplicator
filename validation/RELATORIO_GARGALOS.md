# Relatório — Correção dos Gargalos (pós-validação)

Segunda bateria de 10 vídeos após implementar as 4 prioridades. Comparação
direta com a primeira bateria.

## Comparativo antes × depois

| Métrica | Antes | Depois | Resultado |
|---------|-------|--------|-----------|
| Hook score | 6.4 (todos idênticos) | 6.2–8.45 (7 únicos) | ✅ discrimina |
| Reuso de imagem | 45% (27/60) | 30% (18/60) | ✅ −33% |
| Casos com 0 imagens | 3 | 1 | ✅ −67% |
| Vídeos reais | 2 | 7 | ✅ 3.5× |
| Imagens reais | 40 | 47 | ✅ +18% |
| Visual médio | 8.5 | 9.5 | ✅ |
| Vis. qualidade médio | 6.0 | 7.7 | ✅ |

## Por prioridade

**P1 — Hook Laboratory ✅ ATINGIDO.**
16–18 hooks por vídeo em 6 estratégias. Discriminação real (6.2 a 8.45) e os
hooks específicos vencem os genéricos: Hindenburg "37 Segundos" (8.45), Ponzi
"roubou milhões" (7.95), Sullivan "Sete Raios" (7.55). Eliminou o problema de
hooks idênticos.

**P2 — Asset Acquisition Manager ✅ ATINGIDO (maior impacto).**
ThrottledSession com throttle por domínio + retry + exponential backoff +
cooldown. Era o gargalo nº 1: casos com 0 imagens caíram de 3 → 1; isolado, o
Titanic foi de 83% → 0% de reuso. Confirma que o rate-limit em lote era a causa
raiz da baixa cobertura.

**P3 — Pexels/Pixabay Video ⚠️ PRONTO, requer chave gratuita.**
Suporte completo implementado; vídeo de stock priorizado e tratado como B-roll
contextual. Sem a chave (gratuita), o vídeo fica limitado ao Archive — subiu de
2 → 7 clipes (12% da timeline), mas a meta de 40–60% **só é alcançável com
PEXELS_API_KEY/PIXABAY_API_KEY** (cadastro grátis, sem cartão). É limitação de
fonte, não de código.

**P4 — B-Roll Engine ✅ PARCIAL.**
Busca B-roll contextual (período/local/objeto/emoção, sem âncora estrita) antes
de reusar. Reuso caiu de 45% → 30%. A meta < 15% depende também das fontes extra
(Pexels/Pixabay) para alimentar o B-roll com mais variedade — com o Archive
apenas, parte das cenas de conceito abstrato ainda reusa.

## Gargalos restantes

1. **Volume de requests em lote.** O throttle espaça, mas 10 casos × 6 cenas ×
   N queries × M fontes ainda é alto volume; isolado dá 0% reuso, em lote dá 30%.
   Próximo passo: cache compartilhado entre casos + reduzir queries redundantes.
2. **Vídeo depende de chave gratuita** (Pexels/Pixabay) para atingir 40–60%.
3. **1 caso ainda zera** (Mary Celeste) — âncora restritiva + termo ambíguo.

## Veredito

As 4 prioridades melhoraram **todas as métricas** sem nova arquitetura. Os dois
ganhos estruturais (hook discriminante e fim do rate-limit) estão consolidados.
Os limites restantes (vídeo 40–60% e reuso < 15%) dependem de **ativar as chaves
gratuitas** e de otimização de volume — não de novas features.
