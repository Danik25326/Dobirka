/* Анонімна статистика відвідувань (GoatCounter). Щоб увімкнути: зареєструйтеся на goatcounter.com
   і впишіть код сайту нижче (це частина адреси перед .goatcounter.com). Порожньо — статистика вимкнена. */
(function () {
  var code = "";
  if (!code) return;
  var s = document.createElement("script");
  s.async = true;
  s.setAttribute("data-goatcounter", "https://" + code + ".goatcounter.com/count");
  s.src = "https://gc.zgo.at/count.js";
  document.head.appendChild(s);
})();
