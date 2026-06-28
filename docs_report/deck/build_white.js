// MedServicePrice — белый, острые углы, минимализм (строго по CLAUDE.md).
// Фон белый, текст чёрный, один акцент #3662E3 (цвет логотипа), без градиентов,
// без скруглений (pptx ShapeType.rect = острые углы), без теней.
const PptxGenJS = require("pptxgenjs");
const path = require("path");

const INK = "0A0A0B";   // основной текст
const BODY = "52525B";  // вторичный текст
const MUTE = "9AA1AC";  // подписи, eyebrow
const LINE = "E4E6EA";  // тонкие линии 1px
const ACC = "3662E3";   // единственный акцент (логотип)
const WHITE = "FFFFFF";
const F = "Space Grotesk";
const MONO = "JetBrains Mono";

const LOGO = path.join(__dirname, "logo.png");
const VERIF = path.join(__dirname, "verification.png");

const MX = 0.62;
const W = 13.33, H = 7.5;
const CW = W - 2 * MX;

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "WIDE", width: W, height: H });
pptx.layout = "WIDE";
pptx.author = "Команда 113";
pptx.company = "MedServicePrice";
pptx.title = "MedServicePrice";
pptx.subject = "Единая база услуг и цен клиник партнёров";

function footer(s, page) {
  s.addShape("line", { x: MX, y: 6.95, w: CW, h: 0, line: { color: LINE, width: 1 } });
  s.addImage({ path: LOGO, x: MX, y: 7.04, w: 0.83, h: 0.2 });
  s.addText(`КОМАНДА 113   ·   ${page} / 08`, {
    x: W - MX - 4, y: 7.0, w: 4, h: 0.28, fontFace: F, fontSize: 10,
    color: MUTE, align: "right", charSpacing: 1.5,
  });
}

function head(s, eyebrow, title) {
  s.background = { color: WHITE };
  s.addText(eyebrow, { x: MX, y: 0.52, w: CW, h: 0.3, fontFace: F, fontSize: 11,
    bold: true, color: MUTE, charSpacing: 2.5 });
  s.addText(title, { x: MX, y: 0.86, w: CW, h: 0.85, fontFace: F, fontSize: 30,
    bold: true, color: INK });
}

function box(s, x, y, w, h) {
  s.addShape("rect", { x, y, w, h, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
}

function card(s, x, y, w, h, title, desc) {
  box(s, x, y, w, h);
  s.addText(title, { x: x + 0.22, y: y + 0.18, w: w - 0.44, h: 0.4, fontFace: F,
    fontSize: 14, bold: true, color: INK });
  s.addText(desc, { x: x + 0.22, y: y + 0.62, w: w - 0.44, h: h - 0.74, fontFace: F,
    fontSize: 11, color: BODY, valign: "top", lineSpacingMultiple: 1.12 });
}

function metric(s, x, y, w, h, value, label) {
  box(s, x, y, w, h);
  s.addText(value, { x: x + 0.2, y: y + 0.16, w: w - 0.4, h: h * 0.52, fontFace: F,
    fontSize: 27, bold: true, color: ACC, valign: "top" });
  s.addText(label, { x: x + 0.2, y: y + h - 0.56, w: w - 0.4, h: 0.46, fontFace: F,
    fontSize: 10.5, color: BODY, valign: "top", lineSpacingMultiple: 1.05 });
}

// ---------- 1. Титул ----------
let s = pptx.addSlide();
s.background = { color: WHITE };
s.addText("ХАКАТОН · ТРЕК ДАННЫХ ПРАЙСОВ КЛИНИК", { x: 0, y: 1.55, w: W, h: 0.3,
  fontFace: F, fontSize: 12, bold: true, color: MUTE, align: "center", charSpacing: 3 });
s.addImage({ path: LOGO, x: (W - 3.7) / 2, y: 2.35, w: 3.7, h: 0.89 });
s.addText("Единая база услуг и цен клиник партнёров", { x: 0, y: 3.55, w: W, h: 0.5,
  fontFace: F, fontSize: 21, color: BODY, align: "center" });
s.addShape("line", { x: (W - 3) / 2, y: 4.35, w: 3, h: 0, line: { color: LINE, width: 1 } });
s.addText(
  [
    { text: "Конвейер доверия", options: { color: INK } },
    { text: "      ", options: {} },
    { text: "5 форматов", options: { color: INK } },
    { text: "      ", options: {} },
    { text: "18 435 позиций", options: { color: INK } },
    { text: "      ", options: {} },
    { text: "Происхождение каждой цифры", options: { color: INK } },
  ],
  { x: 0, y: 4.6, w: W, h: 0.4, fontFace: F, fontSize: 13, align: "center" }
);
s.addText("КОМАНДА 113", { x: W - MX - 3, y: 7.0, w: 3, h: 0.28, fontFace: F,
  fontSize: 10, color: MUTE, align: "right", charSpacing: 1.5 });

// ---------- 2. Проблема ----------
s = pptx.addSlide();
head(s, "ПРОБЛЕМА", "Архив прайсов, которому нельзя доверять");
const pcw = (CW - 3 * 0.3) / 4, py = 2.15, ph = 4.4;
card(s, MX + 0 * (pcw + 0.3), py, pcw, ph, "Пять форматов",
  "PDF, DOCX, XLS, XLSX и сканы. У каждой клиники свой шаблон, преамбулы и многоуровневые цены.");
card(s, MX + 1 * (pcw + 0.3), py, pcw, ph, "Битый OCR",
  "Текстовый слой повреждён: «Прейскурант иен» вместо «цен». Клиники 2 и 3 требуют переOCR.");
card(s, MX + 2 * (pcw + 0.3), py, pcw, ph, "Разные названия",
  "Одна услуга записана по-разному. ОАК и общий анализ крови нужно свести к одному эталону.");
card(s, MX + 3 * (pcw + 0.3), py, pcw, ph, "Нет единой базы",
  "Цены нельзя сравнить, нет истории и версий. Каждое число без происхождения и проверки.");
footer(s, "02");

// ---------- 3. Архитектура ----------
s = pptx.addSlide();
head(s, "АРХИТЕКТУРА", "Конвейер доверия");
const stages = [
  ["Маршрутизатор", "формат и скан"],
  ["Экстракторы", "Strategy, 5 форматов"],
  ["Нормализация", "каскад 0-5"],
  ["PostgreSQL", "pgvector + FTS"],
  ["FastAPI", "14 эндпоинтов"],
  ["React UI", "очередь оператора"],
];
const bw = (CW - 5 * 0.34) / 6, by = 2.25, bh = 1.05;
stages.forEach((st, i) => {
  const x = MX + i * (bw + 0.34);
  box(s, x, by, bw, bh);
  s.addText(st[0], { x: x + 0.04, y: by + 0.22, w: bw - 0.08, h: 0.4, fontFace: F,
    fontSize: 11, bold: true, color: INK, align: "center" });
  s.addText(st[1], { x: x + 0.06, y: by + 0.6, w: bw - 0.12, h: 0.35, fontFace: F,
    fontSize: 9, color: MUTE, align: "center" });
  if (i < stages.length - 1)
    s.addText("→", { x: x + bw, y: by + 0.32, w: 0.34, h: 0.4, fontFace: F,
      fontSize: 14, color: ACC, align: "center" });
});
box(s, MX, 3.75, CW, 0.7);
s.addText(
  [
    { text: "AI-слой   ", options: { bold: true, color: ACC } },
    { text: "эмбеддинги (pgvector) · реранк (Cohere) · LLM-арбитр (gpt-4o-mini) — с graceful fallback, без ключа уровень пропускается", options: { color: BODY } },
  ],
  { x: MX + 0.22, y: 3.75, w: CW - 0.44, h: 0.7, fontFace: F, fontSize: 12, valign: "middle" }
);
box(s, MX, 4.65, CW, 0.7);
s.addText(
  [
    { text: "Обработка   ", options: { bold: true, color: ACC } },
    { text: "загрузка через FastAPI · асинхронный разбор документов через Celery + Redis · хранение и история в PostgreSQL", options: { color: BODY } },
  ],
  { x: MX + 0.22, y: 4.65, w: CW - 0.44, h: 0.7, fontFace: F, fontSize: 12, valign: "middle" }
);
s.addText("СТЕК   FastAPI · PostgreSQL / pgvector · Celery / Redis · React + Vite · Docker",
  { x: MX, y: 5.7, w: CW, h: 0.4, fontFace: MONO, fontSize: 11, color: MUTE, charSpacing: 1 });
footer(s, "03");

// ---------- 4. Извлечение ----------
s = pptx.addSlide();
head(s, "ИЗВЛЕЧЕНИЕ · КРИТЕРИЙ 30%", "Пять форматов, реальный хаос");
const exItems = [
  ["ПереOCR битых сканов", "Tesseract rus там, где текстовый слой повреждён (Клиники 2 и 3)."],
  ["Таблицы без линий", "Колонки восстанавливаются по координатам слов, а не по разметке."],
  [".xls через LibreOffice", "Старый формат конвертируется в xlsx; при сбое мягкий фолбэк."],
  ["Tracked changes в DOCX", "Правки принимаются: удаления вырезаются, вставки разворачиваются."],
  ["Склейка многострочных имён", "Перенесённые названия услуг собираются в одну позицию."],
  ["Многоуровневые цены", "Резидент, нерезидент и страховой тариф разбираются по колонкам."],
];
const exX = MX, exW = 7.4;
exItems.forEach((it, i) => {
  const y = 2.1 + i * 0.74;
  s.addText("—", { x: exX, y: y, w: 0.3, h: 0.4, fontFace: F, fontSize: 13, bold: true, color: ACC });
  s.addText(
    [
      { text: it[0] + ".  ", options: { bold: true, color: INK } },
      { text: it[1], options: { color: BODY } },
    ],
    { x: exX + 0.32, y: y - 0.02, w: exW - 0.32, h: 0.66, fontFace: F, fontSize: 12.5, valign: "top", lineSpacingMultiple: 1.04 }
  );
});
const exMx = 8.3, exMw = CW - (exMx - MX);
metric(s, exMx, 2.1, exMw, 1.05, "18 435", "извлечённых позиций");
metric(s, exMx, 3.27, exMw, 1.05, "10 / 8", "файлов / клиник");
metric(s, exMx, 4.44, exMw, 1.05, "5", "форматов прайсов");
footer(s, "04");

// ---------- 5. Нормализация ----------
s = pptx.addSlide();
head(s, "НОРМАЛИЗАЦИЯ · КРИТЕРИЙ 25%", "Каскад с graceful fallback");
const levels = [
  ["0", "Код тарификатора", "детерминированный матч, уверенность 0.98"],
  ["1", "Точное имя", "после нормализации и раскрытия аббревиатур"],
  ["2", "Fuzzy (RapidFuzz)", "авто при сходстве ≥ 0.92"],
  ["3", "Эмбеддинги (pgvector)", "recall по смыслу, top-20 кандидатов"],
  ["4", "Реранк (Cohere)", "уточнение порядка кандидатов"],
  ["5", "LLM-арбитр (gpt-4o-mini)", "спорная зона 0.60 – 0.85"],
];
const lvX = MX, lvW = 6.5;
levels.forEach((lv, i) => {
  const y = 2.1 + i * 0.66;
  s.addShape("rect", { x: lvX, y: y, w: 0.42, h: 0.42, fill: { color: ACC }, line: { color: ACC, width: 1 } });
  s.addText(lv[0], { x: lvX, y: y, w: 0.42, h: 0.42, fontFace: F, fontSize: 14, bold: true, color: WHITE, align: "center", valign: "middle" });
  s.addText(
    [
      { text: lv[1] + "   ", options: { bold: true, color: INK } },
      { text: lv[2], options: { color: MUTE, fontSize: 10.5 } },
    ],
    { x: lvX + 0.6, y: y, w: lvW - 0.6, h: 0.42, fontFace: F, fontSize: 13, valign: "middle" }
  );
});
const mX = 7.45, mW = (CW - (mX - MX) - 0.3) / 2, mH = 1.5;
metric(s, mX, 2.1, mW, mH, "27.59%", "авто по всем активным позициям");
metric(s, mX + mW + 0.3, 2.1, mW, mH, "38.04%", "по адресуемому знаменателю");
metric(s, mX, 2.1 + mH + 0.3, mW, mH, "96.6%", "точность авто-матчей");
metric(s, mX + mW + 0.3, 2.1 + mH + 0.3, mW, mH, "$0.16", "стоимость прогона арбитра");
s.addText("Без ключей каскад деградирует мягко: код, точное, fuzzy и поиск работают офлайн.",
  { x: MX, y: 6.35, w: CW, h: 0.4, fontFace: F, fontSize: 11.5, color: MUTE });
footer(s, "05");

// ---------- 6. Валидация + API ----------
s = pptx.addSlide();
head(s, "ВАЛИДАЦИЯ 20% · API 15%", "Проверки, версии, поиск");
const colW = (CW - 0.4) / 2;
card(s, MX, 2.1, colW, 4.5, "Доверие к данным",
  "");
const vlist = [
  "Проверки ТЗ: цена > 0, нерезидент ≥ резидент, дата не из будущего.",
  "Детектор аномалий: скачок цены более 50% уходит на проверку.",
  "Бессрочное версионирование: ничего не удаляется, ведётся история.",
  "Дедупликация одинаковых позиций по дате.",
];
vlist.forEach((t, i) => s.addText(t, { x: MX + 0.22, y: 2.62 + i * 0.52, w: colW - 0.44, h: 0.5,
  fontFace: F, fontSize: 11.5, color: BODY, bullet: { code: "2022", indent: 14 }, valign: "top" }));
s.addText(
  [
    { text: "Демо истории:  ", options: { bold: true, color: INK } },
    { text: "14 400 ₸ (2024, DOCX)  →  16 600 ₸ (2026, PDF)", options: { color: ACC, bold: true } },
  ],
  { x: MX + 0.22, y: 5.75, w: colW - 0.44, h: 0.5, fontFace: F, fontSize: 12.5, valign: "top" });

card(s, MX + colW + 0.4, 2.1, colW, 4.5, "API и поиск", "");
const alist = [
  "14 REST-эндпоинтов, авто-документация OpenAPI / Swagger на /docs.",
  "Русский полнотекстовый поиск по услугам и партнёрам.",
  "История цен по партнёру и услуге, дашборд качества.",
  "192 теста зелёные, CI на каждый пуш.",
];
alist.forEach((t, i) => s.addText(t, { x: MX + colW + 0.62, y: 2.62 + i * 0.52, w: colW - 0.44, h: 0.5,
  fontFace: F, fontSize: 11.5, color: BODY, bullet: { code: "2022", indent: 14 }, valign: "top" }));
s.addText("GET /search   ·   GET /stats   ·   POST /match   ·   GET /partners/{id}/services/{sid}/history",
  { x: MX + colW + 0.62, y: 5.75, w: colW - 0.5, h: 0.5, fontFace: MONO, fontSize: 9.5, color: MUTE, valign: "top", lineSpacingMultiple: 1.1 });
footer(s, "06");

// ---------- 7. UX оператора ----------
s = pptx.addSlide();
head(s, "UX ОПЕРАТОРА · КРИТЕРИЙ 10%", "Человек в контуре");
const uxItems = [
  ["Очередь верификации", "Три колонки: источник, извлечённые данные, кандидаты с уверенностью."],
  ["Горячие клавиши", "Подтвердить, отклонить, исправить и выбрать кандидата с клавиатуры."],
  ["Дашборд качества", "Метрики в реальном времени: матч, форматы, клиники, очереди."],
  ["Поиск и партнёры", "Полнотекстовый поиск и страница партнёра с историей цен."],
];
uxItems.forEach((it, i) => {
  const y = 2.2 + i * 1.02;
  s.addText("—", { x: MX, y: y, w: 0.3, h: 0.4, fontFace: F, fontSize: 13, bold: true, color: ACC });
  s.addText(it[0], { x: MX + 0.32, y: y - 0.04, w: 4.7, h: 0.4, fontFace: F, fontSize: 14, bold: true, color: INK });
  s.addText(it[1], { x: MX + 0.32, y: y + 0.34, w: 4.7, h: 0.6, fontFace: F, fontSize: 11, color: BODY, valign: "top", lineSpacingMultiple: 1.08 });
});
// скриншот «денежного экрана» (светлый UI, без сайдбара) в тонкой рамке, острые углы
const shW = 5.66, shH = shW * (2000 / 2600), shX = 6.5, shY = 2.12;
s.addShape("rect", { x: shX - 0.04, y: shY - 0.04, w: shW + 0.08, h: shH + 0.08, fill: { color: WHITE }, line: { color: LINE, width: 1 } });
s.addImage({ path: VERIF, x: shX, y: shY, w: shW, h: shH });
s.addText("Очередь верификации на реальных данных", { x: shX, y: shY + shH + 0.1, w: shW, h: 0.3, fontFace: F, fontSize: 10, color: MUTE });
footer(s, "07");

// ---------- 8. Итог ----------
s = pptx.addSlide();
head(s, "ИТОГ", "Конвейер доверия, а не парсер прайсов");
const stats = [
  ["5", "форматов"],
  ["18 435", "позиций"],
  ["10 / 8", "файлов / клиник"],
  ["1231", "услуга в справочнике"],
  ["27.59%", "авто-нормализации"],
  ["96.6%", "точность арбитра"],
  ["14", "эндпоинтов API"],
  ["192", "теста зелёные"],
];
const gw = (CW - 3 * 0.3) / 4, gh = 1.2;
stats.forEach((st, i) => {
  const x = MX + (i % 4) * (gw + 0.3);
  const y = 2.1 + Math.floor(i / 4) * (gh + 0.3);
  metric(s, x, y, gw, gh, st[0], st[1]);
});
const diffs = [
  "Происхождение каждой цифры: файл, страница, строка, уверенность, история.",
  "Гибридный AI-каскад с graceful fallback, а не один парсер.",
  "Живой отчёт о качестве вместо статичной таблицы.",
];
diffs.forEach((t, i) => s.addText(t, { x: MX, y: 5.35 + i * 0.45, w: CW, h: 0.42, fontFace: F,
  fontSize: 12.5, color: INK, bullet: { code: "2022", indent: 16 }, valign: "top" }));
footer(s, "08");

pptx.writeFile({ fileName: process.argv[2] }).then((f) => console.log("wrote", f));
