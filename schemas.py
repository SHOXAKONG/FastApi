from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    role: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: int

class ProductOrder(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_id: int
    products: list[ProductOrder]

class OrderResponse(BaseModel):
    id: int
    customer_id: int
    status: str
    products: list[ProductOrder]

    class Config:
        orm_mode = True