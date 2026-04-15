"""
Seed script: creates 5 restaurants, 4 categories, 50 catalog items,
1 admin, 5 cooks (one per restaurant), 2 buyers, 1 warehouse, 1 driver,
1 curator. Also sets default_buyer_id on each category.
Run: docker compose exec backend python seed.py
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import hash_password
from app.config import settings
from app.models.catalog import CatalogItem, Category, UnitType
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole

engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)

RESTAURANTS = [
    ("Ресторан Арена", "пр. Манаса 22", "+996700100001"),
    ("Кафе Бишкек", "ул. Киевская 77", "+996700100002"),
    ("Паб Ирландский", "ул. Токтогула 115", "+996700100003"),
    ("Столовая №1", "ул. Московская 12", "+996700100004"),
    ("Гриль Хаус", "ул. Байтик Батыра 3", "+996700100005"),
]

CATEGORIES = [
    ("Мясо и птица", 1),
    ("Молочка и яйца", 2),
    ("Овощи и зелень", 3),
    ("Бакалея и химия", 4),
]

ITEMS_BY_CATEGORY = {
    "Мясо и птица": [
        ("Говядина", UnitType.kg, ["с костью", "без кости"]),
        ("Свинина шея", UnitType.kg, []),
        ("Курица целая", UnitType.pcs, []),
        ("Куриное филе", UnitType.kg, []),
        ("Куриные бёдра", UnitType.kg, []),
        ("Фарш говяжий", UnitType.kg, []),
        ("Баранина", UnitType.kg, ["с костью", "вырезка"]),
        ("Сосиски", UnitType.pcs, ["молочные", "говяжьи"]),
        ("Бекон", UnitType.packs, []),
        ("Колбаса варёная", UnitType.kg, []),
        ("Печень говяжья", UnitType.kg, []),
        ("Язык говяжий", UnitType.pcs, []),
    ],
    "Молочка и яйца": [
        ("Молоко 3.2%", UnitType.liters, []),
        ("Сливки 33%", UnitType.liters, []),
        ("Масло сливочное", UnitType.kg, []),
        ("Сметана 20%", UnitType.kg, []),
        ("Творог", UnitType.kg, ["9%", "18%"]),
        ("Сыр Российский", UnitType.kg, []),
        ("Сыр Моцарелла", UnitType.kg, []),
        ("Яйцо куриное", UnitType.pcs, ["С0", "С1"]),
        ("Кефир 2.5%", UnitType.liters, []),
        ("Йогурт натуральный", UnitType.kg, []),
    ],
    "Овощи и зелень": [
        ("Картофель", UnitType.kg, []),
        ("Морковь", UnitType.kg, []),
        ("Лук репчатый", UnitType.kg, []),
        ("Помидоры", UnitType.kg, []),
        ("Огурцы", UnitType.kg, []),
        ("Перец болгарский", UnitType.kg, ["красный", "зелёный", "жёлтый"]),
        ("Капуста белокочанная", UnitType.kg, []),
        ("Чеснок", UnitType.kg, []),
        ("Укроп", UnitType.kg, []),
        ("Петрушка", UnitType.kg, []),
        ("Лимон", UnitType.pcs, []),
        ("Свёкла", UnitType.kg, []),
        ("Зелёный лук", UnitType.kg, []),
    ],
    "Бакалея и химия": [
        ("Масло подсолнечное", UnitType.liters, []),
        ("Сахар", UnitType.kg, []),
        ("Соль", UnitType.kg, []),
        ("Мука пшеничная", UnitType.kg, ["высший сорт", "1-й сорт"]),
        ("Рис", UnitType.kg, []),
        ("Гречка", UnitType.kg, []),
        ("Макароны", UnitType.kg, []),
        ("Томатная паста", UnitType.kg, []),
        ("Уксус", UnitType.liters, []),
        ("Средство для посуды Fairy", UnitType.packs, []),
        ("Перчатки одноразовые", UnitType.packs, ["S", "M", "L"]),
        ("Мешки мусорные 120л", UnitType.packs, []),
        ("Фольга пищевая", UnitType.packs, []),
        ("Пищевая плёнка", UnitType.packs, []),
        ("Салфетки бумажные", UnitType.packs, []),
    ],
}


async def seed():
    async with Session() as s:
        # Restaurants
        restaurants = []
        for name, addr, phone in RESTAURANTS:
            r = Restaurant(name=name, address=addr, contact_phone=phone)
            s.add(r)
            restaurants.append(r)
        await s.flush()

        # Categories + Items — collect category objects to assign buyer later
        categories = []
        for (cat_name, sort), items in zip(CATEGORIES, ITEMS_BY_CATEGORY.values()):
            cat = Category(name=cat_name, sort_order=sort)
            s.add(cat)
            await s.flush()
            categories.append(cat)
            for item_name, unit, variants in items:
                s.add(CatalogItem(category_id=cat.id, name=item_name, unit=unit, variants=variants))

        # Admin
        s.add(User(name="Администратор", phone="+996700000000",
                   password_hash=hash_password("admin123"), role=UserRole.admin))

        # Cooks — one per restaurant
        for i, rest in enumerate(restaurants):
            s.add(User(name=f"Повар {i+1}", phone=f"+99670011000{i+1}",
                       password_hash=hash_password("cook123"),
                       role=UserRole.cook, restaurant_id=rest.id))

        # Buyers
        buyer = User(name="Закупщик 1", phone="+996700220001",
                     password_hash=hash_password("buyer123"), role=UserRole.buyer)
        s.add(buyer)
        s.add(User(name="Закупщик 2", phone="+996700220002",
                   password_hash=hash_password("buyer123"), role=UserRole.buyer))

        # Curator
        s.add(User(name="Куратор", phone="+99699000010",
                   password_hash=hash_password("curator123"), role=UserRole.curator))

        # Warehouse
        s.add(User(name="Кладовщик", phone="+996700330001",
                   password_hash=hash_password("warehouse123"), role=UserRole.warehouse))

        # Driver
        s.add(User(name="Водитель", phone="+996700440001",
                   password_hash=hash_password("driver123"), role=UserRole.driver))

        # Flush to get buyer.id, then assign default_buyer_id on every category
        await s.flush()
        for cat in categories:
            cat.default_buyer_id = buyer.id

        await s.commit()
        print("Seed complete.")
        print("Admin:   +996700000000 / admin123")
        print("Cook:    +996700110001 / cook123")
        print("Buyer:   +996700220001 / buyer123")
        print("Curator: +99699000010  / curator123")


asyncio.run(seed())
