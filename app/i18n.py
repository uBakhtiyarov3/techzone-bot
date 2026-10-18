"""Mijozga ko'rinadigan matnlar: o'zbek (uz) va rus (ru). Xodim/menejer paneli o'zbekcha qoladi.

Har bir matnda `{shop}` — do'kon nomi (brend sozlamasidan) avtomatik qo'yiladi.
"""
from .brand import SHOP
from .catalog import norm_lang

T: dict[str, dict[str, str]] = {
    # ---------- umumiy / start ----------
    "choose_lang": {"uz": "🌐 Tilni tanlang / Выберите язык:", "ru": "🌐 Tilni tanlang / Выберите язык:"},
    "lang_saved": {"uz": "✅ Til: O'zbekcha", "ru": "✅ Язык: Русский"},
    "greet": {
        "uz": "👋 Assalomu alaykum, <b>{name}</b>!\n\n<b>{shop}</b> — smartfonlar, noutbuklar va gadjetlar "
              "rasmiy kafolat bilan. O'zbekiston bo'ylab yetkazib beramiz 🚚",
        "ru": "👋 Здравствуйте, <b>{name}</b>!\n\n<b>{shop}</b> — смартфоны, ноутбуки и гаджеты "
              "с официальной гарантией. Доставляем по всему Узбекистану 🚚",
    },
    "account_created": {"uz": "✅ Siz uchun shaxsiy akkaunt avtomatik ochildi.",
                        "ru": "✅ Для вас автоматически создан личный аккаунт."},
    "closed_now": {"uz": "⏸ Hozir buyurtmalar vaqtincha qabul qilinmayapti.",
                   "ru": "⏸ Сейчас заказы временно не принимаются."},
    "after_hours": {"uz": "🌙 Hozir ish vaqtidan tashqari. Buyurtma bersangiz, operator {when} bog'lanadi.",
                    "ru": "🌙 Сейчас нерабочее время. Оформите заказ — оператор свяжется {when}."},
    "how_order": {"uz": "Xarid qilishning qulay usulini tanlang 👇", "ru": "Выберите удобный способ покупки 👇"},
    "ways_mini": {"uz": "✨ <b>Ilova</b> — rasmli katalog, filtrlar, solishtirish va qulay savat.",
                  "ru": "✨ <b>Приложение</b> — каталог с фото, фильтры, сравнение и удобная корзина."},
    "ways_bot": {"uz": "💬 <b>Botning o'zida</b> — tugmalar orqali, shu chatning ichida.",
                 "ru": "💬 <b>Прямо в боте</b> — кнопками, в этом чате."},
    "start_mini_btn": {"uz": "✨ Do'konni ochish", "ru": "✨ Открыть магазин"},
    "start_bot_btn": {"uz": "💬 Botda xarid qilish", "ru": "💬 Покупать в боте"},
    "main_menu": {"uz": "🏠 Asosiy menyu", "ru": "🏠 Главное меню"},
    "open_mini_text": {"uz": "✨ Do'konni ochish uchun pastdagi tugmani bosing 👇",
                       "ru": "✨ Нажмите кнопку ниже, чтобы открыть магазин 👇"},
    "open_mini_btn": {"uz": "✨ Do'konni ochish", "ru": "✨ Открыть магазин"},
    "contact": {
        "uz": "📞 <b>{shop} bilan bog'lanish</b>\n\nTelefon: {phone}\nIsh vaqti: {hours}\n{address}{links}\n"
              "Savollaringizni shu yerga yozib qoldirishingiz ham mumkin.",
        "ru": "📞 <b>Связаться с {shop}</b>\n\nТелефон: {phone}\nВремя работы: {hours}\n{address}{links}\n"
              "Вопросы можно написать прямо сюда.",
    },
    "phone_soon": {"uz": "tez orada qo'shiladi", "ru": "скоро добавим"},
    "address_line": {"uz": "📍 Manzil: {address}\n", "ru": "📍 Адрес: {address}\n"},
    "about": {
        "uz": "⚡️ <b>{shop}</b>\n<i>{tagline}</i>\n\n{about}\n\n"
              "✅ Original mahsulotlar va rasmiy kafolat\n🚚 O'zbekiston bo'ylab yetkazib berish\n"
              "🏬 Do'kondan olib ketish\n💬 Har bir buyurtma bo'yicha jonli chat",
        "ru": "⚡️ <b>{shop}</b>\n<i>{tagline}</i>\n\n{about}\n\n"
              "✅ Оригинальная техника и официальная гарантия\n🚚 Доставка по всему Узбекистану\n"
              "🏬 Самовывоз из магазина\n💬 Живой чат по каждому заказу",
    },
    "feedback_sent": {"uz": "✅ Xabaringiz yuborildi. Tez orada javob beramiz!",
                      "ru": "✅ Сообщение отправлено. Скоро ответим!"},
    "help": {
        "uz": "ℹ️ <b>Yordam</b>\n\n/start — botni qayta ishga tushirish\n/catalog — katalog\n/search — qidiruv\n"
              "/cart — savat\n/orders — buyurtmalarim\n/lang — tilni o'zgartirish\n",
        "ru": "ℹ️ <b>Помощь</b>\n\n/start — перезапустить бота\n/catalog — каталог\n/search — поиск\n"
              "/cart — корзина\n/orders — мои заказы\n/lang — сменить язык\n",
    },
    "reply_from_shop": {"uz": "💬 <b>{shop} javobi:</b>", "ru": "💬 <b>Ответ {shop}:</b>"},

    # ---------- reply tugmalar ----------
    "b_catalog": {"uz": "📱 Katalog", "ru": "📱 Каталог"},
    "b_search": {"uz": "🔍 Qidiruv", "ru": "🔍 Поиск"},
    "b_cart": {"uz": "🛒 Savat", "ru": "🛒 Корзина"},
    "b_orders": {"uz": "📦 Buyurtmalarim", "ru": "📦 Мои заказы"},
    "b_favorites": {"uz": "❤️ Sevimlilar", "ru": "❤️ Избранное"},
    "b_contact": {"uz": "📞 Aloqa", "ru": "📞 Контакты"},
    "b_about": {"uz": "ℹ️ Biz haqimizda", "ru": "ℹ️ О нас"},
    "b_lang": {"uz": "🌐 Til / Язык", "ru": "🌐 Til / Язык"},
    "b_back": {"uz": "⬅️ Asosiy menyu", "ru": "⬅️ Главное меню"},

    # ---------- katalog ----------
    "catalog_title": {"uz": "📱 <b>Katalog</b>\n\nKategoriyani tanlang 👇", "ru": "📱 <b>Каталог</b>\n\nВыберите категорию 👇"},
    "choose_product": {"uz": "Mahsulotni tanlang 👇", "ru": "Выберите товар 👇"},
    "all_brands": {"uz": "Barchasi", "ru": "Все"},
    "cat_empty": {"uz": "Bu bo'limda hozircha mahsulot yo'q.", "ru": "В этом разделе пока нет товаров."},
    "back_cats": {"uz": "⬅️ Kategoriyalar", "ru": "⬅️ Категории"},
    "back": {"uz": "⬅️ Ortga", "ru": "⬅️ Назад"},
    "cart_btn": {"uz": "🛒 Savat ({count} · {sum})", "ru": "🛒 Корзина ({count} · {sum})"},
    "orders_btn": {"uz": "📦 Buyurtmalarim", "ru": "📦 Мои заказы"},
    "mini_inline": {"uz": "✨ Ilovada ochish", "ru": "✨ Открыть в приложении"},
    "from": {"uz": "dan ", "ru": "от "},
    "pcs": {"uz": "{n} ta", "ru": "{n} шт"},
    "add_btn": {"uz": "🛒 Savatga · {sum}", "ru": "🛒 В корзину · {sum}"},
    "added": {"uz": "✅ <b>{item}</b> savatga qo'shildi!", "ru": "✅ <b>{item}</b> добавлен в корзину!"},
    "added_toast": {"uz": "✅ Savatga qo'shildi", "ru": "✅ Добавлено в корзину"},
    "unavailable": {"uz": "Bu mahsulot hozir sotuvda yo'q", "ru": "Этого товара сейчас нет в продаже"},
    "qty_limit": {"uz": "Omborda shuncha qolgan", "ru": "Больше нет на складе"},
    "in_stock": {"uz": "✅ Sotuvda bor", "ru": "✅ В наличии"},
    "low_stock": {"uz": "⚡️ Oz qoldi: {n} ta", "ru": "⚡️ Осталось: {n} шт"},
    "out_of_stock": {"uz": "⛔️ Sotuvda yo'q", "ru": "⛔️ Нет в наличии"},
    "warranty": {"uz": "🛡 Kafolat: {w}", "ru": "🛡 Гарантия: {w}"},
    "specs_btn": {"uz": "📋 Xarakteristikalar", "ru": "📋 Характеристики"},
    "specs_title": {"uz": "📋 <b>{name}</b> — xarakteristikalar", "ru": "📋 <b>{name}</b> — характеристики"},
    "photos_btn": {"uz": "🖼 Rasmlar ({n})", "ru": "🖼 Фото ({n})"},
    "fav_add_btn": {"uz": "🤍 Sevimlilarga", "ru": "🤍 В избранное"},
    "fav_del_btn": {"uz": "❤️ Sevimlilarda", "ru": "❤️ В избранном"},
    "fav_added": {"uz": "❤️ Sevimlilarga qo'shildi", "ru": "❤️ Добавлено в избранное"},
    "fav_removed": {"uz": "Sevimlilardan olib tashlandi", "ru": "Удалено из избранного"},
    "favorites_title": {"uz": "❤️ <b>Sevimlilar</b>", "ru": "❤️ <b>Избранное</b>"},
    "favorites_empty": {"uz": "❤️ Sevimlilar ro'yxati bo'sh.\n\nMahsulot kartasida 🤍 tugmasini bosing.",
                        "ru": "❤️ Список избранного пуст.\n\nНажмите 🤍 в карточке товара."},
    "alert_btn": {"uz": "🔔 Kelganda xabar berish", "ru": "🔔 Сообщить о поступлении"},
    "alert_on": {"uz": "🔔 Sotuvga chiqqanda xabar beramiz", "ru": "🔔 Сообщим, когда появится"},
    "back_in_stock": {"uz": "🔔 <b>Sotuvga chiqdi!</b>\n\n{item} yana mavjud. Tezroq buyurtma bering 👇",
                      "ru": "🔔 <b>Снова в продаже!</b>\n\n{item} снова в наличии. Успейте заказать 👇"},
    "view_btn": {"uz": "👀 Ko'rish", "ru": "👀 Посмотреть"},

    # ---------- qidiruv ----------
    "search_ask": {"uz": "🔍 Nima qidiryapsiz? Model yoki brend nomini yozing (masalan: <i>iPhone 15</i>).",
                   "ru": "🔍 Что ищете? Напишите модель или бренд (например: <i>iPhone 15</i>)."},
    "search_results": {"uz": "🔍 «{q}» bo'yicha natijalar:", "ru": "🔍 Результаты по «{q}»:"},
    "search_empty": {"uz": "🔍 «{q}» bo'yicha hech narsa topilmadi. Boshqacha yozib ko'ring.",
                     "ru": "🔍 По «{q}» ничего не найдено. Попробуйте по-другому."},

    # ---------- savat ----------
    "cart_empty": {"uz": "🛒 Savatingiz bo'sh.\n\nKatalogdan mahsulot tanlang 👇",
                   "ru": "🛒 Корзина пуста.\n\nВыберите товар в каталоге 👇"},
    "to_catalog": {"uz": "📱 Katalogga o'tish", "ru": "📱 Перейти в каталог"},
    "cart_title": {"uz": "🛒 <b>Savat</b>", "ru": "🛒 <b>Корзина</b>"},
    "items_sum": {"uz": "Mahsulotlar", "ru": "Товары"},
    "delivery": {"uz": "Yetkazib berish", "ru": "Доставка"},
    "free": {"uz": "bepul", "ru": "бесплатно"},
    "discount": {"uz": "Chegirma", "ru": "Скидка"},
    "total": {"uz": "Jami", "ru": "Итого"},
    "min_order_warn": {"uz": "⚠️ Minimal buyurtma: {min}.", "ru": "⚠️ Минимальный заказ: {min}."},
    "clear": {"uz": "🗑 Tozalash", "ru": "🗑 Очистить"},
    "catalog_btn": {"uz": "📱 Katalog", "ru": "📱 Каталог"},
    "checkout_btn": {"uz": "✅ Rasmiylashtirish · {sum}", "ru": "✅ Оформить · {sum}"},
    "cart_cleared": {"uz": "🗑 Savat tozalandi.", "ru": "🗑 Корзина очищена."},
    "stock_trimmed": {"uz": "⚠️ Ba'zi mahsulotlar soni ombordagi qoldiqqa moslab kamaytirildi.",
                      "ru": "⚠️ Количество некоторых товаров уменьшено по остатку на складе."},

    # ---------- rasmiylashtirish ----------
    "co_cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отменить оформление"},
    "co_skip": {"uz": "➡️ O'tkazib yuborish", "ru": "➡️ Пропустить"},
    "co_title": {"uz": "📝 <b>Buyurtmani rasmiylashtirish</b>", "ru": "📝 <b>Оформление заказа</b>"},
    "ask_type": {"uz": "Buyurtmani qanday olasiz?", "ru": "Как получите заказ?"},
    "type_delivery": {"uz": "🚚 Yetkazib berish", "ru": "🚚 Доставка"},
    "type_pickup": {"uz": "🏬 Do'kondan olib ketish", "ru": "🏬 Самовывоз из магазина"},
    "ask_name": {"uz": "👤 Qabul qiluvchining <b>ismini</b> yozing:", "ru": "👤 Напишите <b>имя</b> получателя:"},
    "bad_name": {"uz": "Ism 2 dan 64 belgigacha bo'lsin. Qaytadan yozing:",
                 "ru": "Имя должно быть от 2 до 64 символов. Напишите ещё раз:"},
    "ask_phone": {"uz": "📞 <b>Telefon raqamingizni</b> yuboring.\n\nPastdagi tugmani bosing yoki yozing: "
                        "<code>+998 90 123 45 67</code>",
                  "ru": "📞 Отправьте <b>номер телефона</b>.\n\nНажмите кнопку ниже или напишите: "
                        "<code>+998 90 123 45 67</code>"},
    "send_phone_btn": {"uz": "📱 Raqamimni yuborish", "ru": "📱 Отправить мой номер"},
    "bad_phone": {"uz": "❗️ Raqam noto'g'ri. Masalan: <code>+998 90 123 45 67</code>",
                  "ru": "❗️ Неверный номер. Например: <code>+998 90 123 45 67</code>"},
    "ask_region": {"uz": "🗺 <b>Viloyatni tanlang</b> — yetkazish narxi va muddati shunga bog'liq:",
                   "ru": "🗺 <b>Выберите регион</b> — от него зависят стоимость и срок доставки:"},
    "region_line": {"uz": "{name} · {fee} · {eta}", "ru": "{name} · {fee} · {eta}"},
    "ask_address": {"uz": "📍 <b>Yetkazish manzilini</b> yozing (shahar/tuman, ko'cha, uy, mo'ljal) "
                          "yoki joylashuvingizni yuboring:",
                    "ru": "📍 Напишите <b>адрес доставки</b> (город/район, улица, дом, ориентир) "
                          "или отправьте геолокацию:"},
    "send_location_btn": {"uz": "📍 Joylashuvni yuborish", "ru": "📍 Отправить геолокацию"},
    "location_ok": {"uz": "Joylashuv qabul qilindi ✅", "ru": "Геолокация получена ✅"},
    "location_label": {"uz": "📍 Lokatsiya", "ru": "📍 Геолокация"},
    "bad_address": {"uz": "❗️ Manzilni to'liqroq yozing (kamida 5 belgi):",
                    "ru": "❗️ Напишите адрес подробнее (минимум 5 символов):"},
    "ask_comment": {"uz": "💬 <b>Izoh</b> (ixtiyoriy)\n\nMasalan: qo'ng'iroq qilishdan oldin yozing, "
                          "podyezd, qavat yoki qulay vaqt.",
                    "ru": "💬 <b>Комментарий</b> (необязательно)\n\nНапример: напишите перед звонком, "
                          "подъезд, этаж или удобное время."},
    "ask_promo": {"uz": "🎁 <b>Promo-kodingiz bormi?</b>\nKodni yozing yoki o'tkazib yuboring.",
                  "ru": "🎁 <b>Есть промокод?</b>\nНапишите его или пропустите."},
    "promo_ok": {"uz": "✅ Promo-kod qo'llandi: <b>{code}</b> — {label}", "ru": "✅ Промокод применён: <b>{code}</b> — {label}"},
    "ask_payment": {"uz": "💳 <b>To'lov usulini tanlang:</b>", "ru": "💳 <b>Выберите способ оплаты:</b>"},
    "payment_hint": {"uz": "Naqd — qabul qilganda. Karta — buyurtmadan keyin kartaga o'tkazib, chekni yuborasiz.",
                     "ru": "Наличные — при получении. Карта — после заказа переведите на карту и отправьте чек."},
    "pay_cash": {"uz": "💵 Naqd", "ru": "💵 Наличные"},
    "pay_card": {"uz": "💳 Kartaga o'tkazma", "ru": "💳 Перевод на карту"},
    "pay_card_alert": {"uz": "💳 Karta orqali to'lov hozircha o'chirilgan. Naqd to'lovni tanlang.",
                       "ru": "💳 Оплата картой сейчас недоступна. Выберите наличные."},
    "card_pay_info": {"uz": "💳 <b>To'lov: kartaga o'tkazma</b>\n\nBuyurtma <b>{code}</b> uchun <b>{total}</b> ni quyidagi kartaga o'tkazing:\n\n<code>{number}</code>\n{holder}\n\nSo'ng to'lov chekini (skrinshot) yuboring — tekshirib, tasdiqlaymiz.",
                      "ru": "💳 <b>Оплата: перевод на карту</b>\n\nПереведите <b>{total}</b> за заказ <b>{code}</b> на карту:\n\n<code>{number}</code>\n{holder}\n\nЗатем отправьте чек (скриншот) — мы проверим и подтвердим."},
    "copy_card_btn": {"uz": "📋 Karta raqamini nusxalash", "ru": "📋 Скопировать номер карты"},
    "receipt_btn": {"uz": "🧾 Chekni yuborish", "ru": "🧾 Отправить чек"},
    "receipt_ask": {"uz": "🧾 To'lov chekini <b>rasm</b> qilib yuboring (skrinshot yoki foto).",
                    "ru": "🧾 Отправьте чек об оплате <b>фото</b> (скриншот или снимок)."},
    "receipt_need_photo": {"uz": "Iltimos, chekni rasm ko'rinishida yuboring.", "ru": "Пожалуйста, отправьте чек в виде фото."},
    "receipt_sent": {"uz": "🧾 Chek qabul qilindi — <b>tekshirilmoqda</b>. Natijasini shu yerda xabar qilamiz.",
                     "ru": "🧾 Чек получен — <b>проверяется</b>. Результат сообщим здесь."},
    "pay_paid_msg": {"uz": "✅ <b>{code}</b> buyurtmangiz uchun to'lov tasdiqlandi. Rahmat!",
                     "ru": "✅ Оплата заказа <b>{code}</b> подтверждена. Спасибо!"},
    "pay_rejected_msg": {"uz": "❌ <b>{code}</b> buyurtmasi uchun chek rad etildi.\n\n<b>Sabab:</b> {note}\n\nTo'g'ri chekni qayta yuborishingiz mumkin.",
                         "ru": "❌ Чек по заказу <b>{code}</b> отклонён.\n\n<b>Причина:</b> {note}\n\nВы можете отправить правильный чек повторно."},
    "pay_await": {"uz": "⏳ Chek kutilmoqda", "ru": "⏳ Ожидается чек"},
    "pay_review": {"uz": "🧾 Chek tekshirilmoqda", "ru": "🧾 Чек проверяется"},
    "pay_paid": {"uz": "✅ To'landi", "ru": "✅ Оплачено"},
    "pay_rejected": {"uz": "❌ Chek rad etildi", "ru": "❌ Чек отклонён"},
    "e_receipt_closed": {"uz": "Bu buyurtma uchun chek yuborib bo'lmaydi", "ru": "Для этого заказа нельзя отправить чек"},
    "check_title": {"uz": "🧾 <b>Buyurtmani tekshiring</b>", "ru": "🧾 <b>Проверьте заказ</b>"},
    "payment": {"uz": "To'lov", "ru": "Оплата"},
    "confirm_btn": {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить"},
    "refill_btn": {"uz": "✏️ Qaytadan to'ldirish", "ru": "✏️ Заполнить заново"},
    "cancel_btn": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "co_cancelled": {"uz": "Rasmiylashtirish bekor qilindi. Savatingiz saqlanib qoldi 🛒",
                     "ru": "Оформление отменено. Корзина сохранена 🛒"},
    "form_stale": {"uz": "Bu forma eskirgan. Savatdan qaytadan rasmiylashtiring.",
                   "ru": "Эта форма устарела. Оформите заказ заново из корзины."},
    "order_placed": {"uz": "🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\nBuyurtma ID: <code>{code}</code>\nJami: <b>{total}</b>\n\n"
                           "Operator tez orada bog'lanadi. Holat o'zgarganda shu yerda xabar beramiz.",
                     "ru": "🎉 <b>Заказ принят!</b>\n\nНомер заказа: <code>{code}</code>\nИтого: <b>{total}</b>\n\n"
                           "Оператор скоро свяжется с вами. Сообщим здесь, когда статус изменится."},
    "order_sent_toast": {"uz": "✅ Buyurtma yuborildi!", "ru": "✅ Заказ отправлен!"},
    "thanks": {"uz": "Rahmat! 😊", "ru": "Спасибо! 😊"},
    "pickup_from": {"uz": "🏬 Olib ketish: {address}", "ru": "🏬 Самовывоз: {address}"},
    "pickup_shop": {"uz": "do'kondan", "ru": "из магазина"},
    "pickup_location": {"uz": "📍 <b>Olib ketish manzili</b>{address}\n\nXaritadagi nuqtani bosib, yo'nalish olishingiz mumkin.",
                        "ru": "📍 <b>Адрес самовывоза</b>{address}\n\nНажмите на точку на карте, чтобы построить маршрут."},
    "map_btn": {"uz": "🗺 Google Maps'da ochish", "ru": "🗺 Открыть в Google Maps"},
    "eta_line": {"uz": "⏱ Yetkazish muddati: {eta}", "ru": "⏱ Срок доставки: {eta}"},

    # ---------- buyurtmalar ----------
    "no_orders": {"uz": "Sizda hali buyurtmalar yo'q. Katalogga nazar soling! 📱",
                  "ru": "У вас пока нет заказов. Загляните в каталог! 📱"},
    "orders_title": {"uz": "📦 <b>Buyurtmalarim</b>\n\nBatafsil ko'rish uchun tanlang:",
                     "ru": "📦 <b>Мои заказы</b>\n\nВыберите для подробностей:"},
    "order_title": {"uz": "🧾 <b>Buyurtma</b> <code>{code}</code>", "ru": "🧾 <b>Заказ</b> <code>{code}</code>"},
    "reason": {"uz": "Sabab: {reason}", "ru": "Причина: {reason}"},
    "refresh": {"uz": "🔄 Yangilash", "ru": "🔄 Обновить"},
    "refreshed": {"uz": "🔄 Yangilandi", "ru": "🔄 Обновлено"},
    "cancel_order_btn": {"uz": "❌ Buyurtmani bekor qilish", "ru": "❌ Отменить заказ"},
    "repeat_btn": {"uz": "🔁 Qayta buyurtma berish", "ru": "🔁 Повторить заказ"},
    "back_orders": {"uz": "⬅️ Buyurtmalarim", "ru": "⬅️ Мои заказы"},
    "order_not_found": {"uz": "Buyurtma topilmadi", "ru": "Заказ не найден"},
    "cancel_not_allowed": {"uz": "Buyurtma allaqachon qabul qilingan — bekor qilish uchun chatda yozing.",
                           "ru": "Заказ уже принят — для отмены напишите в чат."},
    "order_cancelled_toast": {"uz": "Buyurtma bekor qilindi", "ru": "Заказ отменён"},
    "repeat_added": {"uz": "🔁 Oldingi buyurtma savatga qo'shildi (narxlar joriy).",
                     "ru": "🔁 Прошлый заказ добавлен в корзину (по текущим ценам)."},
    "repeat_none": {"uz": "Afsuski, bu buyurtmadagi mahsulotlar hozir sotuvda yo'q.",
                    "ru": "К сожалению, товаров из этого заказа сейчас нет в продаже."},
    "your_rating": {"uz": "Sizning bahoingiz: {stars}", "ru": "Ваша оценка: {stars}"},
    "rate_btn": {"uz": "⭐ Baholash", "ru": "⭐ Оценить"},
    "warranty_card": {"uz": "🛡 <b>Kafolat</b>", "ru": "🛡 <b>Гарантия</b>"},
    "warranty_until": {"uz": "{item}: {until} gacha{serial}", "ru": "{item}: до {until}{serial}"},
    "media_btn": {"uz": "🖼 Holat rasmlari ({n})", "ru": "🖼 Фото статуса ({n})"},
    "chat_btn": {"uz": "💬 Do'konga yozish", "ru": "💬 Написать магазину"},
    "chat_btn_unread": {"uz": "💬 Chat ({n} yangi)", "ru": "💬 Чат ({n} новых)"},

    # ---------- buyurtma chati ----------
    "chat_ask": {"uz": "💬 <b>{code}</b> buyurtmasi bo'yicha xabaringizni yozing (matn yoki rasm). "
                       "Do'kon xodimi shu yerda javob beradi.",
                 "ru": "💬 Напишите сообщение по заказу <b>{code}</b> (текст или фото). "
                       "Сотрудник магазина ответит здесь."},
    "chat_sent": {"uz": "✅ Xabar yuborildi. Javobni shu yerda olasiz.", "ru": "✅ Сообщение отправлено. Ответ придёт сюда."},
    "chat_history": {"uz": "💬 <b>{code}</b> — yozishma", "ru": "💬 <b>{code}</b> — переписка"},
    "chat_empty": {"uz": "Hali xabarlar yo'q.", "ru": "Сообщений пока нет."},
    "chat_you": {"uz": "Siz", "ru": "Вы"},
    "chat_from_shop": {"uz": "💬 <b>{shop}</b> · buyurtma <code>{code}</code>:\n\n{text}",
                       "ru": "💬 <b>{shop}</b> · заказ <code>{code}</code>:\n\n{text}"},
    "chat_reply_btn": {"uz": "↩️ Javob yozish", "ru": "↩️ Ответить"},
    "chat_end_btn": {"uz": "✅ Tayyor", "ru": "✅ Готово"},

    "chat_closed": {"uz": "Buyurtma yakunlangan — chat yopildi. Savol yoki muammo bo'lsa «⚠️ Muammo haqida xabar "
                          "berish» tugmasidan foydalaning.",
                    "ru": "Заказ завершён — чат закрыт. Если есть вопрос или проблема, нажмите «⚠️ Сообщить о проблеме»."},

    # ---------- qaytarish va muammo xabari ----------
    "issue_btn": {"uz": "⚠️ Muammo haqida xabar berish", "ru": "⚠️ Сообщить о проблеме"},
    "return_btn": {"uz": "↩️ Qaytarish ({date} gacha)", "ru": "↩️ Вернуть (до {date})"},
    "issue_ask": {"uz": "⚠️ <b>{code}</b> buyurtmasi bo'yicha muammo yoki savolingizni yozing. "
                        "Mutaxassisimiz telefon orqali bog'lanadi.",
                  "ru": "⚠️ Опишите проблему или вопрос по заказу <b>{code}</b>. "
                        "Наш специалист свяжется с вами по телефону."},
    "return_ask": {"uz": "↩️ <b>{code}</b> buyurtmasini qaytarish.\n\nQaytarish sababini batafsil yozing "
                         "(nuqson, mos kelmadi, boshqa mahsulot keldi...).",
                   "ru": "↩️ Возврат заказа <b>{code}</b>.\n\nПодробно опишите причину возврата "
                         "(брак, не подошёл, пришёл другой товар...)."},
    "ticket_short": {"uz": "Iltimos, batafsilroq yozing (kamida 10 belgi).",
                     "ru": "Пожалуйста, опишите подробнее (минимум 10 символов)."},
    "ticket_photos": {"uz": "📷 Mahsulot rasmlarini yuboring (5 tagacha). Tayyor bo'lsa «✅ Yuborish» ni bosing.",
                      "ru": "📷 Отправьте фото товара (до 5). Когда готово — нажмите «✅ Отправить»."},
    "ticket_photos_issue": {"uz": "📷 Kerak bo'lsa rasm yuboring (5 tagacha) yoki darhol «✅ Yuborish» ni bosing.",
                            "ru": "📷 При необходимости отправьте фото (до 5) или сразу нажмите «✅ Отправить»."},
    "ticket_photo_ok": {"uz": "📷 {n} ta rasm qabul qilindi.", "ru": "📷 Получено фото: {n}."},
    "ticket_send_btn": {"uz": "✅ Yuborish", "ru": "✅ Отправить"},
    "ticket_need_photo": {"uz": "Qaytarish uchun kamida bitta rasm yuboring.",
                          "ru": "Для возврата отправьте хотя бы одно фото."},
    "ticket_sent": {"uz": "✅ Murojaatingiz qabul qilindi (№{id}). Mutaxassisimiz tez orada telefon orqali bog'lanadi.",
                    "ru": "✅ Обращение принято (№{id}). Специалист скоро свяжется с вами по телефону."},
    "ticket_exists": {"uz": "Bu buyurtma bo'yicha murojaatingiz ko'rib chiqilmoqda. Tez orada bog'lanamiz.",
                      "ru": "Ваше обращение по этому заказу уже рассматривается. Скоро свяжемся."},
    "return_not_allowed": {"uz": "Bu buyurtmani qaytarib bo'lmaydi (muddat tugagan yoki ariza allaqachon berilgan).",
                           "ru": "Этот заказ нельзя вернуть (срок истёк или заявка уже подана)."},
    "ticket_kind_return": {"uz": "Qaytarish", "ru": "Возврат"},
    "ticket_kind_issue": {"uz": "Muammo xabari", "ru": "Сообщение о проблеме"},
    "ticket_open": {"uz": "🕐 Ko'rib chiqilmoqda", "ru": "🕐 На рассмотрении"},
    "ticket_approved": {"uz": "✅ Tasdiqlandi", "ru": "✅ Одобрено"},
    "ticket_rejected": {"uz": "❌ Rad etildi", "ru": "❌ Отклонено"},
    "ticket_resolved": {"uz": "✅ Hal qilindi", "ru": "✅ Решено"},
    "return_approved": {"uz": "✅ <b>{code}</b> buyurtmasini qaytarish tasdiqlandi.{note}",
                        "ru": "✅ Возврат заказа <b>{code}</b> одобрен.{note}"},
    "return_rejected": {"uz": "❌ <b>{code}</b> buyurtmasini qaytarish rad etildi.{note}",
                        "ru": "❌ Возврат заказа <b>{code}</b> отклонён.{note}"},
    "issue_resolved": {"uz": "✅ <b>{code}</b> bo'yicha murojaatingiz hal qilindi.{note}",
                       "ru": "✅ Ваше обращение по заказу <b>{code}</b> решено.{note}"},

    # ---------- bildirishnomalar ----------
    "sent_new": {"uz": "🧾 Buyurtmangiz <code>{code}</code> qabul qilindi!\n\n"
                       "Operator tez orada bog'lanadi. Holat o'zgarganda shu yerda xabar beramiz.",
                 "ru": "🧾 Ваш заказ <code>{code}</code> принят!\n\n"
                       "Оператор скоро свяжется с вами. Сообщим здесь, когда статус изменится."},
    "track_btn": {"uz": "📦 Buyurtmani kuzatish", "ru": "📦 Отследить заказ"},
    "st_accepted": {"uz": "✅ Buyurtmangiz <code>{code}</code> tasdiqlandi!",
                    "ru": "✅ Ваш заказ <code>{code}</code> подтверждён!"},
    "st_packing": {"uz": "📦 Buyurtmangiz <code>{code}</code> yig'ilmoqda...",
                   "ru": "📦 Ваш заказ <code>{code}</code> собирается..."},
    "st_shipping": {"uz": "🚚 Buyurtmangiz <code>{code}</code> yo'lda!{eta}",
                    "ru": "🚚 Ваш заказ <code>{code}</code> в пути!{eta}"},
    "st_shipping_pickup": {"uz": "🛍 Buyurtmangiz <code>{code}</code> tayyor — olib ketishingiz mumkin!{address}",
                           "ru": "🛍 Ваш заказ <code>{code}</code> готов — можно забирать!{address}"},
    "st_delivered": {"uz": "🎉 Buyurtmangiz <code>{code}</code> yetkazildi. Xaridingiz muborak! 😊",
                     "ru": "🎉 Ваш заказ <code>{code}</code> доставлен. Поздравляем с покупкой! 😊"},
    "st_delivered_pickup": {"uz": "🎉 Buyurtmangiz <code>{code}</code> topshirildi. Xaridingiz muborak! 😊",
                            "ru": "🎉 Ваш заказ <code>{code}</code> выдан. Поздравляем с покупкой! 😊"},
    "st_cancelled": {"uz": "❌ Afsuski, buyurtmangiz <code>{code}</code> bekor qilindi.{reason}\n"
                           "Savollar bo'lsa, biz bilan bog'laning.",
                     "ru": "❌ К сожалению, ваш заказ <code>{code}</code> отменён.{reason}\nЕсли есть вопросы — свяжитесь с нами."},
    "status_photo": {"uz": "📸 Buyurtma <code>{code}</code> · {status}", "ru": "📸 Заказ <code>{code}</code> · {status}"},

    # ---------- baholash ----------
    "rate_ask": {"uz": "⭐ <b>Xaridingizni baholang!</b>\nFikringiz biz uchun juda muhim.",
                 "ru": "⭐ <b>Оцените покупку!</b>\nВаше мнение очень важно для нас."},
    "rate_thanks": {"uz": "Rahmat! 🙏 {stars}\n\nIzoh qoldirasizmi? Yozing yoki «O'tkazib yuborish»ni bosing.",
                    "ru": "Спасибо! 🙏 {stars}\n\nОставите комментарий? Напишите или нажмите «Пропустить»."},
    "review_saved": {"uz": "✅ Fikringiz uchun rahmat! Sizni yana kutamiz 😊",
                     "ru": "✅ Спасибо за отзыв! Ждём вас снова 😊"},
    "already_rated": {"uz": "Bu buyurtma allaqachon baholangan", "ru": "Этот заказ уже оценён"},
    "rate_not_ready": {"uz": "Buyurtma hali yakunlanmagan", "ru": "Заказ ещё не завершён"},

    # ---------- holatlar (mijoz uchun) ----------
    "s_new": {"uz": "🕐 Tasdiqlash kutilmoqda", "ru": "🕐 Ожидает подтверждения"},
    "s_accepted": {"uz": "✅ Qabul qilindi", "ru": "✅ Принят"},
    "s_packing": {"uz": "📦 Yig'ilmoqda", "ru": "📦 Собирается"},
    "s_shipping": {"uz": "🚚 Yo'lda", "ru": "🚚 В пути"},
    "s_shipping_pickup": {"uz": "🛍 Tayyor — olib ketishingiz mumkin", "ru": "🛍 Готов — можно забирать"},
    "s_delivered": {"uz": "🎉 Yetkazildi", "ru": "🎉 Доставлен"},
    "s_delivered_pickup": {"uz": "🎉 Topshirildi", "ru": "🎉 Выдан"},
    "s_cancelled": {"uz": "❌ Bekor qilindi", "ru": "❌ Отменён"},
    "s_returned": {"uz": "↩️ Qaytarildi", "ru": "↩️ Возвращён"},
    "step_new": {"uz": "Buyurtma berildi", "ru": "Заказ оформлен"},

    # ---------- xatolar (OrderError) ----------
    "e_empty_cart": {"uz": "Savat bo'sh", "ru": "Корзина пуста"},
    "e_too_many": {"uz": "Savatda juda ko'p mahsulot", "ru": "Слишком много позиций в корзине"},
    "e_cart": {"uz": "Savatda xato bor", "ru": "Ошибка в корзине"},
    "e_qty": {"uz": "Mahsulot soni 1 dan 20 gacha bo'lishi kerak", "ru": "Количество — от 1 до 20"},
    "e_unavailable": {"uz": "Savatdagi ba'zi mahsulotlar endi sotuvda yo'q. Savatni yangilang.",
                      "ru": "Некоторых товаров из корзины больше нет в продаже. Обновите корзину."},
    "e_stock": {"uz": "«{item}» omborda {left} ta qoldi. Sonini kamaytiring.",
                "ru": "«{item}» на складе осталось {left} шт. Уменьшите количество."},
    "e_closed_full": {"uz": "Hozir buyurtma qabul qilinmayapti.", "ru": "Сейчас заказы не принимаются."},
    "e_name": {"uz": "Qabul qiluvchi ismini kiriting", "ru": "Укажите имя получателя"},
    "e_phone": {"uz": "Telefon raqam noto'g'ri. Format: +998 90 123 45 67",
                "ru": "Неверный телефон. Формат: +998 90 123 45 67"},
    "e_region": {"uz": "Yetkazish viloyatini tanlang", "ru": "Выберите регион доставки"},
    "e_address": {"uz": "Manzilni to'liqroq kiriting", "ru": "Укажите адрес подробнее"},
    "e_card": {"uz": "Karta orqali to'lov hozircha o'chirilgan. Naqd to'lovni tanlang.",
               "ru": "Оплата картой сейчас недоступна. Выберите наличные."},
    "e_payment": {"uz": "To'lov usulini tanlang", "ru": "Выберите способ оплаты"},
    "e_min_order": {"uz": "Minimal buyurtma: {min}", "ru": "Минимальный заказ: {min}"},
    "e_cooldown": {"uz": "Iltimos, biroz kuting va qayta urinib ko'ring", "ru": "Подождите немного и попробуйте снова"},
    "e_type": {"uz": "Bu olish usuli hozir mavjud emas", "ru": "Этот способ получения сейчас недоступен"},
    "e_promo_not_found": {"uz": "Bunday promo-kod topilmadi", "ru": "Промокод не найден"},
    "e_promo_inactive": {"uz": "Bu promo-kod faol emas", "ru": "Промокод неактивен"},
    "e_promo_not_started": {"uz": "Bu promo-kod hali boshlanmagan", "ru": "Промокод ещё не действует"},
    "e_promo_expired": {"uz": "Bu promo-kodning muddati tugagan", "ru": "Срок действия промокода истёк"},
    "e_promo_min": {"uz": "Bu promo-kod {min} dan ortiq buyurtmaga amal qiladi",
                    "ru": "Промокод действует на заказ от {min}"},
    "e_promo_limit": {"uz": "Bu promo-kod limiti tugagan", "ru": "Лимит использования промокода исчерпан"},
    "e_promo_user_limit": {"uz": "Siz bu promo-koddan allaqachon foydalangansiz", "ru": "Вы уже использовали этот промокод"},
    "e_promo_first": {"uz": "Bu promo-kod faqat birinchi buyurtma uchun", "ru": "Промокод только для первого заказа"},
    "e_promo_pickup": {"uz": "Bu promo-kod faqat yetkazib berish uchun", "ru": "Промокод только для доставки"},

    # ---------- promo turlari ----------
    "promo_percent": {"uz": "-{value}% chegirma", "ru": "скидка {value}%"},
    "promo_fixed": {"uz": "-{value} chegirma", "ru": "скидка {value}"},
    "promo_free_delivery": {"uz": "bepul yetkazib berish", "ru": "бесплатная доставка"},
}

# ---------- Mini App matnlari (w_ prefiksi bilan T ga qo'shiladi) ----------
W: dict[str, dict[str, str]] = {
    "tabHome": {"uz": "Asosiy", "ru": "Главная"},
    "tabCatalog": {"uz": "Katalog", "ru": "Каталог"},
    "tabCart": {"uz": "Savat", "ru": "Корзина"},
    "tabFav": {"uz": "Sevimli", "ru": "Избранное"},
    "tabOrders": {"uz": "Buyurtmalar", "ru": "Заказы"},
    "search": {"uz": "Smartfon, noutbuk, brend...", "ru": "Смартфон, ноутбук, бренд..."},
    "searchEmpty": {"uz": "Hech narsa topilmadi", "ru": "Ничего не найдено"},
    "categories": {"uz": "Kategoriyalar", "ru": "Категории"},
    "brands": {"uz": "Brendlar", "ru": "Бренды"},
    "hits": {"uz": "Xit savdo", "ru": "Хиты продаж"},
    "newArrivals": {"uz": "Yangi kelganlar", "ru": "Новинки"},
    "deals": {"uz": "Chegirmalar", "ru": "Скидки"},
    "seeAll": {"uz": "Barchasi", "ru": "Все"},
    "allProducts": {"uz": "Barcha mahsulotlar", "ru": "Все товары"},
    "perk1": {"uz": "Original va kafolat", "ru": "Оригинал и гарантия"},
    "perk2": {"uz": "O'zbekiston bo'ylab yetkazish", "ru": "Доставка по Узбекистану"},
    "perk3": {"uz": "Har buyurtmada jonli chat", "ru": "Живой чат по заказу"},
    "filters": {"uz": "Filtr", "ru": "Фильтры"},
    "sort": {"uz": "Saralash", "ru": "Сортировка"},
    "sortPopular": {"uz": "Mashhur", "ru": "Популярные"},
    "sortNew": {"uz": "Yangi", "ru": "Новые"},
    "sortCheap": {"uz": "Arzonroq", "ru": "Дешевле"},
    "sortExpensive": {"uz": "Qimmatroq", "ru": "Дороже"},
    "price": {"uz": "Narx", "ru": "Цена"},
    "priceFrom": {"uz": "dan", "ru": "от"},
    "priceTo": {"uz": "gacha", "ru": "до"},
    "inStockOnly": {"uz": "Faqat sotuvdagilar", "ru": "Только в наличии"},
    "withDiscount": {"uz": "Chegirmadagilar", "ru": "Со скидкой"},
    "reset": {"uz": "Tozalash", "ru": "Сбросить"},
    "show": {"uz": "Ko'rsatish", "ru": "Показать"},
    "found": {"uz": "{n} ta mahsulot", "ru": "{n} товаров"},
    "from": {"uz": "dan", "ru": "от"},
    "inStock": {"uz": "Sotuvda bor", "ru": "В наличии"},
    "lowStock": {"uz": "Oz qoldi: {n} ta", "ru": "Осталось: {n} шт"},
    "lowStockShort": {"uz": "Oz qoldi", "ru": "Мало"},
    "outOfStock": {"uz": "Sotuvda yo'q", "ru": "Нет в наличии"},
    "notify": {"uz": "Kelganda xabar berish", "ru": "Сообщить о поступлении"},
    "notifyOn": {"uz": "Sotuvga chiqqanda botda xabar beramiz", "ru": "Сообщим в боте, когда появится"},
    "warranty": {"uz": "Kafolat", "ru": "Гарантия"},
    "specs": {"uz": "Xarakteristikalar", "ru": "Характеристики"},
    "description": {"uz": "Tavsif", "ru": "Описание"},
    "showAll": {"uz": "Hammasini ko'rsatish", "ru": "Показать все"},
    "addToCart": {"uz": "Savatga", "ru": "В корзину"},
    "inCart": {"uz": "Savatda", "ru": "В корзине"},
    "goCart": {"uz": "Savatga o'tish", "ru": "Перейти в корзину"},
    "added": {"uz": "Savatga qo'shildi", "ru": "Добавлено в корзину"},
    "favAdded": {"uz": "Sevimlilarga qo'shildi", "ru": "Добавлено в избранное"},
    "favEmpty": {"uz": "Yoqqan mahsulotlarni ❤️ bilan saqlang", "ru": "Сохраняйте понравившиеся товары ❤️"},
    "compare": {"uz": "Solishtirish", "ru": "Сравнение"},
    "compareAdd": {"uz": "Solishtirishga", "ru": "К сравнению"},
    "compareAdded": {"uz": "Solishtirishga qo'shildi", "ru": "Добавлено к сравнению"},
    "compareLimit": {"uz": "4 tagacha mahsulotni solishtirish mumkin", "ru": "Можно сравнить до 4 товаров"},
    "compareEmpty": {"uz": "Solishtirish uchun mahsulot kartasida ⇄ ni bosing",
                     "ru": "Нажмите ⇄ в карточке товара, чтобы сравнить"},
    "compareClear": {"uz": "Tozalash", "ru": "Очистить"},
    "onlyDiff": {"uz": "Faqat farqlar", "ru": "Только различия"},
    "cart": {"uz": "Savat", "ru": "Корзина"},
    "clear": {"uz": "Tozalash", "ru": "Очистить"},
    "clearConfirm": {"uz": "Savatni tozalaysizmi?", "ru": "Очистить корзину?"},
    "checkout": {"uz": "Rasmiylashtirish", "ru": "Оформить заказ"},
    "checkoutTitle": {"uz": "Buyurtma berish", "ru": "Оформление"},
    "notAccepting": {"uz": "Hozir buyurtma qabul qilinmayapti", "ru": "Сейчас заказы не принимаются"},
    "afterHours": {"uz": "Ish vaqtidan tashqari — operator {time} bog'lanadi", "ru": "Нерабочее время — оператор свяжется {time}"},
    "emptyCart": {"uz": "Savatingiz bo'sh", "ru": "Корзина пуста"},
    "emptyCartSub": {"uz": "Katalogdan o'zingizga yoqqan texnikani tanlang", "ru": "Выберите технику в каталоге"},
    "toCatalog": {"uz": "Katalogga o'tish", "ru": "Перейти в каталог"},
    "items": {"uz": "Mahsulotlar", "ru": "Товары"},
    "deliveryFee": {"uz": "Yetkazib berish", "ru": "Доставка"},
    "free": {"uz": "bepul", "ru": "бесплатно"},
    "discount": {"uz": "Chegirma", "ru": "Скидка"},
    "total": {"uz": "Jami", "ru": "Итого"},
    "minOrder": {"uz": "Minimal buyurtma: {sum}. Yana {left} qo'shing.",
                 "ru": "Минимальный заказ: {sum}. Добавьте ещё {left}."},
    "freeFrom": {"uz": "{sum} dan bepul yetkazamiz", "ru": "Бесплатная доставка от {sum}"},
    "delivery": {"uz": "Yetkazib berish", "ru": "Доставка"},
    "pickup": {"uz": "Olib ketish", "ru": "Самовывоз"},
    "pickupFrom": {"uz": "Buyurtmani do'kondan olib ketasiz", "ru": "Заберёте заказ в магазине"},
    "openMap": {"uz": "Xaritada ochish", "ru": "Открыть на карте"},
    "region": {"uz": "Viloyat", "ru": "Регион"},
    "regionPh": {"uz": "Viloyatni tanlang", "ru": "Выберите регион"},
    "eta": {"uz": "Muddat", "ru": "Срок"},
    "name": {"uz": "Qabul qiluvchi ismi", "ru": "Имя получателя"},
    "namePh": {"uz": "Ismingiz", "ru": "Ваше имя"},
    "phone": {"uz": "Telefon raqam", "ru": "Телефон"},
    "address": {"uz": "Manzil", "ru": "Адрес"},
    "addressPh": {"uz": "Shahar/tuman, ko'cha, uy, mo'ljal", "ru": "Город/район, улица, дом, ориентир"},
    "geo": {"uz": "Joriy joylashuvimni qo'shish", "ru": "Добавить мою геолокацию"},
    "geoLoading": {"uz": "Aniqlanmoqda...", "ru": "Определяем..."},
    "geoAdded": {"uz": "Joylashuv qo'shildi", "ru": "Геолокация добавлена"},
    "geoFail": {"uz": "Joylashuvni aniqlab bo'lmadi", "ru": "Не удалось определить геолокацию"},
    "comment": {"uz": "Izoh (ixtiyoriy)", "ru": "Комментарий (необязательно)"},
    "commentPh": {"uz": "Qo'ng'iroqdan oldin yozing, qavat, qulay vaqt...", "ru": "Напишите перед звонком, этаж, удобное время..."},
    "promo": {"uz": "Promo-kod", "ru": "Промокод"},
    "promoPh": {"uz": "Kodni kiriting", "ru": "Введите код"},
    "apply": {"uz": "Qo'llash", "ru": "Применить"},
    "remove": {"uz": "Olib tashlash", "ru": "Убрать"},
    "payment": {"uz": "To'lov usuli", "ru": "Способ оплаты"},
    "cash": {"uz": "Naqd", "ru": "Наличные"},
    "cashSub": {"uz": "Qabul qilganda", "ru": "При получении"},
    "card": {"uz": "Kartaga o'tkazma", "ru": "Перевод на карту"},
    "cardSub": {"uz": "Buyurtmadan so'ng chek yuborasiz", "ru": "После заказа отправите чек"},
    "soon": {"uz": "O'chirilgan", "ru": "Недоступно"},
    "cardSoon": {"uz": "Karta orqali to'lov hozircha o'chirilgan", "ru": "Оплата картой сейчас недоступна"},
    "payTitle": {"uz": "Kartaga o'tkazma", "ru": "Перевод на карту"},
    "payHint": {"uz": "Summani shu kartaga o'tkazing va to'lov chekini (skrinshot) yuklang.", "ru": "Переведите сумму на эту карту и загрузите чек (скриншот)."},
    "copy": {"uz": "Nusxalash", "ru": "Копировать"},
    "copied": {"uz": "Nusxalandi", "ru": "Скопировано"},
    "chooseReceipt": {"uz": "Chek rasmini tanlang", "ru": "Выберите фото чека"},
    "sendReceipt": {"uz": "Chekni yuborish", "ru": "Отправить чек"},
    "receiptSent": {"uz": "Chek yuborildi — tekshirilmoqda", "ru": "Чек отправлен — проверяется"},
    "payAwait": {"uz": "Chek kutilmoqda", "ru": "Ожидается чек"},
    "payReview": {"uz": "Chek tekshirilmoqda", "ru": "Чек проверяется"},
    "payReviewSub": {"uz": "Tekshirib, natijasini xabar qilamiz", "ru": "Проверим и сообщим результат"},
    "payPaid": {"uz": "To'landi", "ru": "Оплачено"},
    "payRejected": {"uz": "Chek rad etildi", "ru": "Чек отклонён"},
    "resend": {"uz": "Qayta yuborish", "ru": "Отправить снова"},
    "confirm": {"uz": "Buyurtmani tasdiqlash", "ru": "Подтвердить заказ"},
    "sending": {"uz": "Yuborilmoqda...", "ru": "Отправляем..."},
    "errName": {"uz": "Qabul qiluvchi ismini kiriting", "ru": "Укажите имя получателя"},
    "errPhone": {"uz": "Telefon raqamni to'liq kiriting: +998 90 123 45 67", "ru": "Введите номер полностью: +998 90 123 45 67"},
    "errRegion": {"uz": "Viloyatni tanlang", "ru": "Выберите регион"},
    "errAddress": {"uz": "Manzilni to'liqroq kiriting", "ru": "Укажите адрес подробнее"},
    "placed": {"uz": "Buyurtma qabul qilindi!", "ru": "Заказ принят!"},
    "orderId": {"uz": "Buyurtma ID", "ru": "Номер заказа"},
    "placedSub": {"uz": "Operator tez orada bog'lanadi. Holatni shu yerda va botda kuzating.",
                  "ru": "Оператор скоро свяжется. Следите за статусом здесь и в боте."},
    "track": {"uz": "Buyurtmani kuzatish", "ru": "Отследить заказ"},
    "continueShopping": {"uz": "Xaridni davom ettirish", "ru": "Продолжить покупки"},
    "myOrders": {"uz": "Buyurtmalarim", "ru": "Мои заказы"},
    "noOrders": {"uz": "Hali buyurtmalar yo'q", "ru": "Заказов пока нет"},
    "ordersBack": {"uz": "Buyurtmalar", "ru": "Заказы"},
    "pcs": {"uz": "ta", "ru": "шт"},
    "stepNew": {"uz": "Buyurtma berildi", "ru": "Заказ оформлен"},
    "cancelOrder": {"uz": "Buyurtmani bekor qilish", "ru": "Отменить заказ"},
    "cancelConfirm": {"uz": "Buyurtmani bekor qilasizmi?", "ru": "Отменить заказ?"},
    "cancelledToast": {"uz": "Buyurtma bekor qilindi", "ru": "Заказ отменён"},
    "cancelledTitle": {"uz": "Buyurtma bekor qilindi", "ru": "Заказ отменён"},
    "reason": {"uz": "Sabab", "ru": "Причина"},
    "statusPhotos": {"uz": "Holat rasmlari", "ru": "Фото статуса"},
    "warrantyCard": {"uz": "Kafolat kartasi", "ru": "Гарантийный талон"},
    "warrantyUntil": {"uz": "{date} gacha", "ru": "до {date}"},
    "serial": {"uz": "IMEI / SN", "ru": "IMEI / SN"},
    "chat": {"uz": "Chat", "ru": "Чат"},
    "chatTitle": {"uz": "Do'kon bilan chat", "ru": "Чат с магазином"},
    "chatPh": {"uz": "Xabar yozing...", "ru": "Напишите сообщение..."},
    "chatEmpty": {"uz": "Buyurtma bo'yicha savolingizni yozing — xodim shu yerda javob beradi.",
                  "ru": "Задайте вопрос по заказу — сотрудник ответит здесь."},
    "you": {"uz": "Siz", "ru": "Вы"},
    "chatClosed": {"uz": "Buyurtma yakunlangan — chat yopildi", "ru": "Заказ завершён — чат закрыт"},
    "issue": {"uz": "Muammo haqida xabar berish", "ru": "Сообщить о проблеме"},
    "issueHint": {"uz": "Muammo yoki savolingizni yozing — mutaxassis telefon orqali bog'lanadi.",
                  "ru": "Опишите проблему или вопрос — специалист свяжется по телефону."},
    "returnOrder": {"uz": "Buyurtmani qaytarish", "ru": "Вернуть заказ"},
    "returnUntil": {"uz": "{date} gacha qaytarish mumkin", "ru": "Вернуть можно до {date}"},
    "returnHint": {"uz": "Sababini batafsil yozing va mahsulot rasmlarini yuklang.",
                   "ru": "Подробно опишите причину и загрузите фото товара."},
    "reasonPh": {"uz": "Nima bo'ldi? Batafsil yozing...", "ru": "Что случилось? Опишите подробно..."},
    "addPhotos": {"uz": "Rasm qo'shish", "ru": "Добавить фото"},
    "photoRequired": {"uz": "Kamida bitta rasm yuklang", "ru": "Загрузите хотя бы одно фото"},
    "reasonShort": {"uz": "Batafsilroq yozing (kamida 10 belgi)", "ru": "Опишите подробнее (минимум 10 символов)"},
    "send": {"uz": "Yuborish", "ru": "Отправить"},
    "ticketSent": {"uz": "Murojaat qabul qilindi. Tez orada bog'lanamiz!", "ru": "Обращение принято. Скоро свяжемся!"},
    "tickets": {"uz": "Murojaatlar", "ru": "Обращения"},
    "ticketKind_return": {"uz": "Qaytarish", "ru": "Возврат"},
    "ticketKind_issue": {"uz": "Muammo xabari", "ru": "Сообщение о проблеме"},
    "ticketSt_open": {"uz": "Ko'rib chiqilmoqda", "ru": "На рассмотрении"},
    "ticketSt_approved": {"uz": "Tasdiqlandi", "ru": "Одобрено"},
    "ticketSt_rejected": {"uz": "Rad etildi", "ru": "Отклонено"},
    "ticketSt_resolved": {"uz": "Hal qilindi", "ru": "Решено"},
    "rateTitle": {"uz": "Xaridni baholang", "ru": "Оцените покупку"},
    "ratePh": {"uz": "Izoh (ixtiyoriy)", "ru": "Комментарий (необязательно)"},
    "rateSend": {"uz": "Yuborish", "ru": "Отправить"},
    "rateThanks": {"uz": "Rahmat! Fikringiz biz uchun muhim", "ru": "Спасибо за отзыв!"},
    "yourRating": {"uz": "Sizning bahoingiz", "ru": "Ваша оценка"},
    "questions": {"uz": "Savollar uchun", "ru": "По вопросам"},
    "retry": {"uz": "Qayta urinish", "ru": "Повторить"},
    "openInTg": {"uz": "Iltimos, ilovani Telegram bot orqali oching.", "ru": "Пожалуйста, откройте приложение через Telegram-бота."},
    "network": {"uz": "Internet aloqasini tekshiring", "ru": "Проверьте интернет-соединение"},
    "back": {"uz": "Ortga", "ru": "Назад"},
    "chooseOption": {"uz": "Variantni tanlang", "ru": "Выберите вариант"},
    "unavailableCombo": {"uz": "Bu kombinatsiya mavjud emas", "ru": "Такой комбинации нет"},
    "maxQty": {"uz": "Omborda shuncha qolgan", "ru": "Больше нет на складе"},
}
T.update({f"w_{k}": v for k, v in W.items()})


# Admin paneldan tahrirlangan matnlar: {(kalit, til): matn}. Saqlanganda darhol yangilanadi.
OVERRIDES: dict[tuple[str, str], str] = {}


def set_overrides(rows: list[dict]) -> None:
    OVERRIDES.clear()
    OVERRIDES.update({(r["key"], r["lang"]): r["value"] for r in rows if r["key"] in T})


def default_text(key: str, lang: str) -> str:
    entry = T.get(key) or {}
    return entry.get(lang) or entry.get("uz") or key


def _fill(text: str, kw: dict) -> str:
    if "{" not in text:
        return text
    return text.format(**kw)


def t(key: str, lang: str = "uz", **kw) -> str:
    if key not in T:
        return key
    lang = norm_lang(lang)
    kw.setdefault("shop", SHOP["name"])
    text = OVERRIDES.get((key, lang)) or default_text(key, lang)
    try:
        return _fill(text, kw)
    except (KeyError, IndexError, ValueError):
        # tahrirlangan matnda xato bo'lsa — asl matn (bot to'xtab qolmasin)
        return _fill(default_text(key, lang), kw)


def placeholders(text: str) -> set[str]:
    import string

    try:
        return {name for _, name, _, _ in string.Formatter().parse(text) if name}
    except ValueError:
        return {"<xato>"}


def web_texts(lang: str) -> dict[str, str]:
    """Mini App uchun barcha matnlar (tahrirlanganlari bilan). {n}, {sum} kabi o'zgaruvchilar JS da qo'yiladi."""
    out = {}
    for k in T:
        if k.startswith("w_"):
            text = OVERRIDES.get((k, norm_lang(lang))) or default_text(k, norm_lang(lang))
            out[k[2:]] = text.replace("{shop}", SHOP["name"])
    return out


def both(key: str) -> set[str]:
    """Reply tugma matnini ikkala tilda (handler filtrlari uchun), tahrirlanganlari ham."""
    return {t(key, "uz"), t(key, "ru"), *T[key].values()}


def money_l(amount: int | float, lang: str = "uz") -> str:
    s = f"{int(amount):,}".replace(",", " ")
    return f"{s} сум" if norm_lang(lang) == "ru" else f"{s} so'm"


def ticket_status(status: str, lang: str) -> str:
    return t(f"ticket_{status}", lang)


def status_text(status: str, order_type: str, lang: str) -> str:
    if order_type == "pickup" and status in ("shipping", "delivered"):
        return t(f"s_{status}_pickup", lang)
    return t(f"s_{status}", lang)


def stars(n: int) -> str:
    return "⭐" * int(n)
