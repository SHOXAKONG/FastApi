from fastapi import FastAPI, Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from schemas import ProductCreate, OrderCreate
from utils import authenticate_user, create_access_token, get_current_admin_user, get_current_user, get_db, \
    get_password_hash
from db import engine, Base
from models import User, Product, Order, OrderDetail

app = FastAPI()

Base.metadata.create_all(bind=engine)

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
        username: str,
        fullname: str,
        password: str,
        email: str,
        role: str,
        db: Session = Depends(get_db)
):

    allowed_roles = ["customer"]

    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Allowed roles are: {', '.join(allowed_roles)}"
        )

    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    hashed_password = get_password_hash(password)

    new_user = User(username=username, full_name=fullname, hashed_password=hashed_password, email=email, role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"detail": "User registered successfully"}

# Admin Endpoints
@admin_router.post("/products", response_model=ProductCreate)
async def create_product(
        product: ProductCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    new_product = Product(**product.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product


@admin_router.get("/products/{id}", response_model=ProductCreate)
async def read_product(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    product = db.query(Product).filter(Product.id == id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@admin_router.put("/products/{id}", response_model=ProductCreate)
async def update_product(
        id: int,
        product: ProductCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    db_product = db.query(Product).filter(Product.id == id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in product.dict().items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product


@admin_router.delete("/products/{id}")
async def delete_product(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    db_product = db.query(Product).filter(Product.id == id).first()
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(db_product)
    db.commit()
    return {"detail": "Product deleted"}


@admin_router.get("/orders")
async def read_orders(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    orders = db.query(Order).all()
    return orders


@admin_router.get("/orders/{id}")
async def read_order(
        id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_admin_user)
):
    order = db.query(Order).filter(Order.id == id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


customer_router = APIRouter(
    prefix="/customer",
    tags=["Customer"]
)


# Customer Endpoints
@customer_router.get("/products")
async def read_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return products


@customer_router.post("/orders")
async def create_order(
        order: OrderCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # Validate Products
    for product in order.products:
        db_product = db.query(Product).filter(Product.id == product.product_id).first()
        if not db_product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product.product_id} not found"
            )
        if product.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quantity for product ID {product.product_id}"
            )

    # Create Order
    new_order = Order(customer_id=current_user.id, status="Pending")
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    # Add Order Details
    for product in order.products:
        order_detail = OrderDetail(
            order_id=new_order.id,
            product_id=product.product_id,
            quantity=product.quantity
        )
        db.add(order_detail)
    db.commit()
    db.refresh(new_order)  # Refresh to include relationships

    return {
        "id": new_order.id,
        "customer_id": new_order.customer_id,
        "status": new_order.status,
        "details": [
            {
                "product_id": detail.product_id,
                "quantity": detail.quantity,
                "product_name": detail.product.name,
                "product_price": detail.product.price
            } for detail in new_order.order_details
        ]
    }


@customer_router.get("/orders/{customerId}")
async def read_customer_orders(
        customerId: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    orders = db.query(Order).filter(Order.customer_id == customerId).all()
    return orders


@customer_router.get("/orders/{orderId}/status")
async def read_order_status(
        orderId: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    order = db.query(Order).filter(Order.id == orderId).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": order.status}


app.include_router(admin_router)
app.include_router(customer_router)