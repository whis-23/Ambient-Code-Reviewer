
# Legacy API endpoints (Testing ADR-01 Violation)
from fastapi import FastAPI, Depends

app = FastAPI()

@app.get("/api/deleteUser")
def delete_user(user_id: int):
    # VIOLATION: ADR-01 says use DELETE /api/v1/users/{id}
    # It also says version via URL path, not missing version!
    return {"status": "User deleted"}

@app.post("/api/v1/create_order")
def create_order(data: dict):
    # VIOLATION: ADR-01 says use snake_case Resource names like /api/v1/orders
    return {"order_id": 123}
