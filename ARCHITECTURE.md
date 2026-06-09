# StoryReplicator v2.0 — Arquitetura Completa

## Visão Geral

Sistema Python que transforma uma URL de vídeo viral do YouTube em um novo vídeo
original, pronto para publicação em YouTube Shorts, TikTok, Instagram Reels e Facebook Reels.

Nicho: **Histórias Reais Inacreditáveis**

---

## Estrutura de Arquivos

```
autovideo/
├── main.py                          ← Orquestrador principal (ponto de entrada)
├── config.py                        ← Configurações globais + VIDEO_MODES
├── requirements.txt
├── install.bat                      ← Instalação automática Windows
├── run.bat                          ← Atalho de execução Windows
├── ARCHITECTURE.md                  ← Este arquivo
│
└── modules/
    ├── extractor.py                 ← ETAPA 01: Extração YouTube
    ├── analyzer.py                  ← ETAPA 02: Análise narrativa
    ├── story_generator.py           ← ETAPA 03: Nova história original
    ├── script_writer.py             ← ETAPA 04: Roteiro com timecodes
    ├── narration_writer.py          ← ETAPA 05: Narração para TTS
    ├── storyboard_generator.py      ← ETAPA 06: Storyboard visual
    ├── image_acquisition_engine.py  ← ETAPA 07: Busca + download de imagens ★ NOVO
    ├── visual_prompts.py            ← ETAPA 08: Prompts para imagens faltantes
    ├── timeline_builder.py          ← ETAPA 09: timeline.json + subtitles.srt
    ├── tts_engine.py                ← ETAPA 10: Kokoro TTS → audio.wav
    ├── publisher_metadata.py        ← ETAPA 11: Títulos, hashtags, thumbnail
    └── video_assembler.py           ← ETAPA 12: FFmpeg → final_video.mp4
```

---

## Fluxo Completo v2.0

```
URL YouTube
    │
    ▼ ETAPA 01 — extractor.py
    │  yt-dlp + youtube-transcript-api
    │  → título, descrição, transcrição, duração, views, comentários
    │  → 01_video_data.json
    │
    ▼ ETAPA 02 — analyzer.py
    │  Claude API → análise estrutura narrativa
    │  → hook, contexto, conflito, escalada, plot_twist, encerramento
    │  → por_que_viral, formula_replicavel
    │  → 02_analysis.json
    │
    ▼ ETAPA 03 — story_generator.py
    │  Claude API → NOVA HISTÓRIA ORIGINAL (mesma fórmula, outro evento)
    │  → titulo, logline, personagem, epoca_local, estrutura
    │  → 03_story.json
    │
    ▼ ETAPA 04 — script_writer.py  [MODE-AWARE]
    │  Claude API → roteiro com timecodes dinâmicos por modo
    │  → segmentos com narration_lines + direção visual
    │  → 04_script.json
    │
    ▼ ETAPA 05 — narration_writer.py  [MODE-AWARE]
    │  Claude API → narração limpa otimizada para TTS
    │  → texto corrido PT-BR, números por extenso, sem símbolos
    │  → 05_narration.json
    │
    ▼ ETAPA 06 — storyboard_generator.py  [MODE-AWARE]
    │  Claude API → storyboard visual completo
    │  → cena a cena: descrição visual, ângulo, movimento, legenda
    │  → 06_storyboard.json
    │
    ▼ ETAPA 07 — image_acquisition_engine.py  ★ NOVO
    │  1. Claude API → keywords para TODAS as cenas (1 chamada batch)
    │  2. Busca automática em 3 fontes:
    │     ├─ Wikimedia Commons  (domínio público + licenças livres)
    │     ├─ Library of Congress (acervo histórico americano)
    │     └─ Internet Archive   (vasto domínio público)
    │  3. Score por: keyword match (40%) + subjects (20%)
    │                período histórico (20%) + resolução (20%)
    │  4. Download + conversão JPEG + cache 7 dias
    │  5. → assets/image_01.jpg ... image_NN.jpg
    │  6. → 08_acquisition_report.json
    │  7. → missing_assets.json  (se houver cenas sem imagem)
    │
    ▼ ETAPA 08 — visual_prompts.py
    │  Claude API → prompts detalhados em inglês para imagens faltantes
    │  (National Geographic / Cinematic / 8K / Film Grain)
    │  → 08_visual_prompts.json
    │  → 08_image_prompts.txt  (legível para uso manual)
    │
    ▼ ETAPA 09 — timeline_builder.py
    │  Monta timeline.json usando imagens adquiridas na Etapa 07
    │  Gera subtitles.srt sincronizado
    │  → timeline.json
    │  → subtitles.srt
    │
    ▼ ETAPA 10 — tts_engine.py
    │  Kokoro TTS — 3 backends em cascata:
    │  1. kokoro-onnx  (local, offline, qualidade alta)
    │  2. kokoro PyPI  (alternativo)
    │  3. edge-tts     (Microsoft Azure PT-BR, online)
    │  → audio.wav
    │
    ▼ ETAPA 11 — publisher_metadata.py
    │  Claude API → metadados de publicação multi-plataforma
    │  → títulos (YouTube/TikTok/Instagram/Facebook)
    │  → descrição, hashtags, thumbnail prompt, CTA
    │  → 11_metadata.json
    │  → 11_metadata.txt
    │
    ▼ ETAPA 12 — video_assembler.py
       FFmpeg: imagens + Ken Burns + áudio + legendas queimadas
       → final_video.mp4  (1080x1920, H.264, AAC)
```

---

## Modos de Duração  ★ NOVO

| Modo         | Duração | Palavras | Segmentos                                          | Uso                             |
|--------------|---------|----------|----------------------------------------------------|---------------------------------|
| `short`      | 60s     | ~150     | hook→contexto→conflito→escalada→plot_twist→cta    | YouTube Shorts, TikTok **PADRÃO** |
| `reel`       | 90s     | ~225     | hook→contexto→conflito→escalada→plot_twist→final→cta | Instagram/Facebook Reels      |
| `documentary`| 120s    | ~300     | hook→contexto→conflito→escalada→plot_twist→final→cta | Documentário curto completo   |

### Timecodes por modo

**SHORT (60s):**
```
0–3s    HOOK
3–10s   CONTEXTO
10–28s  CONFLITO
28–48s  ESCALADA
48–55s  PLOT TWIST
55–60s  CTA
```

**REEL (90s):**
```
0–3s    HOOK
3–12s   CONTEXTO
12–35s  CONFLITO
35–62s  ESCALADA
62–76s  PLOT TWIST
76–86s  FINAL
86–90s  CTA
```

**DOCUMENTARY (120s):**
```
0–3s     HOOK
3–15s    CONTEXTO
15–45s   CONFLITO
45–70s   ESCALADA
70–90s   PLOT TWIST
90–110s  FINAL
110–120s CTA
```

---

## Image Acquisition Engine — Detalhes

### Fontes de imagem (gratuitas, domínio público)

| Fonte | API | Acervo | Melhor para |
|---|---|---|---|
| Wikimedia Commons | REST + MediaWiki API | 100M+ arquivos | Qualquer época, global |
| Library of Congress | JSON API | Fotos históricas EUA séc. XIX-XX | Eventos americanos |
| Internet Archive | Advanced Search API | Milhões de itens | Retratos, documentos, jornais |

### Sistema de Score (0.0 → 1.0)

```
score = keyword_match  × 0.40   # queries presentes no título/descrição
      + subject_match  × 0.20   # sujeitos específicos (pessoas, objetos)
      + period_match   × 0.20   # década/era histórica
      + resolution     × 0.20   # megapixels / 4.0 (cap em 1.0)
```

### Cache local

```
output/<slug>/
└── cache/
    ├── metadata/   ← resultados de busca em JSON (TTL 7 dias)
    └── downloads/  ← imagens brutas baixadas (TTL 7 dias)
```

### Relatórios gerados

| Arquivo | Conteúdo |
|---|---|
| `08_acquisition_report.json` | total, found, missing, success_rate, fonte por cena, score |
| `missing_assets.json` | cenas sem imagem, keywords tentadas, sugestão de busca manual |

---

## Arquivos gerados por execução

```
output/<slug>/
├── 01_video_data.json        ← dados brutos do YouTube
├── 02_analysis.json          ← análise narrativa
├── 03_story.json             ← nova história
├── 04_script.json            ← roteiro com timecodes
├── 05_narration.json         ← narração TTS
├── 06_storyboard.json        ← storyboard cena a cena
├── 08_acquisition_report.json ← relatório de busca de imagens
├── missing_assets.json        ← imagens não encontradas (se houver)
├── 08_visual_prompts.json     ← prompts para imagens faltantes
├── 08_image_prompts.txt       ← prompts legíveis (uso manual)
├── timeline.json              ← timeline completo para montagem
├── subtitles.srt              ← legendas sincronizadas
├── audio.wav                  ← narração sintetizada
├── 11_metadata.json           ← metadados de publicação
├── 11_metadata.txt            ← títulos + hashtags (cópia/cola)
├── assets/
│   ├── image_01.jpg           ← imagens por cena (auto-adquiridas ou placeholder)
│   ├── image_02.jpg
│   └── ...
├── cache/
│   ├── metadata/              ← cache de buscas (7 dias)
│   └── downloads/             ← cache de downloads (7 dias)
└── final_video.mp4            ← vídeo final renderizado
```

---

## Como usar

### Instalação

```bat
install.bat
```

### Configurar API Key

```bat
set ANTHROPIC_API_KEY=sk-ant-...
```

### Exemplos de uso

```bat
REM Modo padrão (short, 60s):
python main.py https://youtu.be/XXXXX

REM Reel 90s:
python main.py https://youtu.be/XXXXX --mode reel

REM Documentário 120s:
python main.py https://youtu.be/XXXXX --mode documentary

REM Sem montar vídeo (gerar assets apenas):
python main.py https://youtu.be/XXXXX --skip-video

REM Sem busca automática de imagens:
python main.py https://youtu.be/XXXXX --skip-images

REM Combinado — só gerar textos e prompts:
python main.py https://youtu.be/XXXXX --skip-video --skip-images

REM Pasta personalizada:
python main.py https://youtu.be/XXXXX --output-dir C:\meus_videos\ep01
```

---

## Dependências

| Pacote | Versão | Status | Uso |
|---|---|---|---|
| anthropic | ≥0.40 | ❌ instalar | Claude API (etapas 2-6, 8, 11) |
| yt-dlp | ≥2024 | ✅ instalado | Extração YouTube |
| youtube-transcript-api | ≥0.6 | ❌ instalar | Transcrição |
| requests | ≥2.31 | incluso | Image Acquisition |
| Pillow | ≥10 | ❌ instalar | Conversão JPEG |
| kokoro-onnx | ≥0.4 | ❌ instalar | TTS principal |
| edge-tts | ≥6.1 | ❌ instalar | TTS fallback |
| numpy | ≥1.24 | ✅ instalado | Audio processing |
| soundfile | ≥0.12 | ❌ instalar | Salvar WAV |
| onnxruntime | ≥1.23 | ✅ instalado | Kokoro backend |
| ffmpeg | binário | ❌ instalar | Montagem de vídeo |

### Instalar dependências faltantes

```bat
pip install anthropic youtube-transcript-api requests Pillow kokoro-onnx edge-tts soundfile
```

### Instalar FFmpeg (Windows)

1. Baixar: https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip`
2. Descompactar em `C:\ffmpeg\`
3. Adicionar `C:\ffmpeg\bin` ao PATH do sistema

---

## Ambiente verificado

- Python: 3.10.11 64-bit
- GPU: AMD Radeon RX 550 (CPU-only para TTS)
- RAM: 48 GB total
- Disco livre: ~130 GB
- ONNX Runtime: 1.23.2 (CPUExecutionProvider)
