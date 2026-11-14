/* Канали для прямих ефірів. Використовують і головна сторінка (віджет), і live.html.
   name — назва на кнопці; channelId — ідентифікатор каналу YouTube (починається з UC…); url — сторінка каналу.
   Без channelId канал показується лише на сторінці live.html як посилання на YouTube.
   Де взяти channelId: YouTube на комп’ютері → сторінка каналу → «Про канал» → «Поділитися» → «Скопіювати ідентифікатор каналу». */
window.CHANNELS = [
  { name: "Суспільне Новини", channelId: "UCPY6gj8G7dqwPxg9KwHrj5Q", url: "https://www.youtube.com/@SuspilneNews" },
  { name: "24 Канал", channelId: "UCja992VI_u2e52c9FHQXw5A", url: "https://www.youtube.com/channel/UCja992VI_u2e52c9FHQXw5A" },
  { name: "5 канал", channelId: "", url: "https://www.youtube.com/5channel" }
];
