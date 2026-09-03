"""示例数据初始化脚本。可重复运行（先清空再插入）。"""
import logging
import random
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.database import Base, sync_engine
from app.models.demo_data import Product, Order, OrderItem
from app.users.models import Role
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


PRODUCTS = [
    # 电子产品
    ("iPhone 15", "电子产品", 5999.0),
    ("MacBook Air", "电子产品", 8999.0),
    ("AirPods Pro", "电子产品", 1899.0),
    ("iPad Mini", "电子产品", 3799.0),
    ("机械键盘", "电子产品", 599.0),
    # 服装
    ("运动T恤", "服装", 129.0),
    ("牛仔裤", "服装", 299.0),
    ("羽绒服", "服装", 899.0),
    ("运动鞋", "服装", 499.0),
    ("棒球帽", "服装", 79.0),
    # 食品
    ("进口牛奶", "食品", 68.0),
    ("坚果礼盒", "食品", 128.0),
    ("有机鸡蛋", "食品", 39.0),
    ("精品咖啡", "食品", 89.0),
    # 家居
    ("台灯", "家居", 199.0),
    ("收纳箱", "家居", 49.0),
    ("四件套", "家居", 399.0),
    # 运动
    ("瑜伽垫", "运动", 99.0),
    ("跑步机", "运动", 2999.0),
    ("哑铃套装", "运动", 299.0),
]

CUSTOMERS = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
             "郑一", "冯二", "陈明", "林华", "黄强", "刘洋", "杨帆"]


def seed():
    Base.metadata.drop_all(sync_engine)
    Base.metadata.create_all(sync_engine)

    with Session(sync_engine) as session:
        # 初始化角色
        import json
        roles_data = [
            ("admin", "超级管理员", json.dumps(["*"])),
            ("editor", "编辑者", json.dumps(["agent:query", "agent:schemas"])),
            ("viewer", "查看者", json.dumps(["agent:schemas"])),
        ]
        for name, desc, perms in roles_data:
            role = Role(name=name, description=desc, permissions=perms)
            session.add(role)
        session.flush()
        logger.info(f"已创建 {len(roles_data)} 个角色")

        # 插入商品
        products = []
        for name, category, price in PRODUCTS:
            p = Product(name=name, category=category, price=price)
            products.append(p)
        session.add_all(products)
        session.flush()

        # 生成订单（跨最近 3 个月）
        today = date.today()
        start_date = today - timedelta(days=90)
        orders = []
        for i in range(100):
            order_date = start_date + timedelta(days=random.randint(0, 89))
            customer = random.choice(CUSTOMERS)
            o = Order(customer_name=customer, order_date=order_date, status="completed")
            orders.append(o)
        session.add_all(orders)
        session.flush()

        # 生成订单明细
        for order in orders:
            n_items = random.randint(1, 5)
            chosen = random.sample(products, n_items)
            for product in chosen:
                qty = random.randint(1, 5)
                oi = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=product.price,
                )
                session.add(oi)

        session.commit()
        logger.info(f"已插入 {len(products)} 个商品, {len(orders)} 个订单")


if __name__ == "__main__":
    seed()
