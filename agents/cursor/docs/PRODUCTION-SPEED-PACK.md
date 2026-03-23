---
# === SUITE 6 CANONICAL HEADER ===
suite: "Cursor Governance Suite 6 (L9 + Suite 6)"
version: "6.0.0"
component_id: "DOC-PSP-001"
component_name: "Production Speed Pack"
layer: "documentation"
domain: "development_productivity"
type: "guide"
status: "active"
created: "2025-11-07T00:00:00Z"
updated: "2026-01-04T00:00:00Z"
author: "Igor Beylin"
maintainer: "Igor Beylin"

# === GOVERNANCE METADATA ===
governance_level: "informational"
compliance_required: false
audit_trail: false
security_classification: "internal"

# === BUSINESS METADATA ===
title: "Production Speed Pack v1.0.0"
purpose: "Code templates and patterns for rapid production-ready development"
summary: >
  Comprehensive collection of production-ready code templates, refactoring patterns,
  performance optimization strategies, and debugging approaches. Extracted from
  CursorPreferencePack to accelerate development velocity while maintaining quality.
business_value: "Accelerates development with production-ready templates"
# === LEGACY METADATA (preserved) ===
tags:
  ["production", "templates", "patterns", "performance", "debugging", "speed"]
production_ready: true
---

# Production Speed Pack

## Purpose

Accelerate development with production-ready templates and patterns. No placeholders, full error handling, optimized for speed and quality.

---

## A. Code Generation Templates

### 1. FastAPI Endpoint Template

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(prefix="/api/v1", tags=["resource"])
logger = logging.getLogger(__name__)

class ResourceCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ResourceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: str

@router.post("/resources", response_model=ResourceResponse, status_code=201)
async def create_resource(
    resource: ResourceCreate,
    db = Depends(get_db)
) -> ResourceResponse:
    """
    Create a new resource.

    Args:
        resource: Resource creation data
        db: Database session

    Returns:
        Created resource with ID and timestamp

    Raises:
        HTTPException: 400 if validation fails, 500 if database error
    """
    try:
        # Implementation
        result = await db.insert(resource)
        return ResourceResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 2. React Component Template

```typescript
import React, { useState, useEffect } from 'react';

interface ResourceProps {
  id: number;
  onUpdate?: (resource: Resource) => void;
}

interface Resource {
  id: number;
  name: string;
  description?: string;
}

export const ResourceCard: React.FC<ResourceProps> = ({ id, onUpdate }) => {
  const [resource, setResource] = useState<Resource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchResource = async () => {
      try {
        const response = await fetch(`/api/v1/resources/${id}`);
        if (!response.ok) throw new Error('Failed to fetch resource');
        const data = await response.json();
        setResource(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchResource();
  }, [id]);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!resource) return null;

  return (
    <div className="resource-card">
      <h3>{resource.name}</h3>
      {resource.description && <p>{resource.description}</p>}
    </div>
  );
};
```

---

### 3. PostgreSQL Schema Template

```sql
-- Resources table with full constraints and indexes
CREATE TABLE resources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT resources_status_check CHECK (status IN ('active', 'inactive', 'archived'))
);

-- Indexes for common queries
CREATE INDEX idx_resources_owner_id ON resources(owner_id);
CREATE INDEX idx_resources_status ON resources(status);
CREATE INDEX idx_resources_created_at ON resources(created_at DESC);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_resources_updated_at
    BEFORE UPDATE ON resources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## B. Refactoring Patterns

### 1. Extract Function Pattern

**Trigger**: Function > 50 lines

```python
# Before
def process_order(order):
    # Validate
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Negative total")

    # Calculate
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * 0.08
    total = subtotal + tax

    # Save
    db.save(order)

# After
def process_order(order):
    validate_order(order)
    order.total = calculate_order_total(order)
    save_order(order)

def validate_order(order):
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Negative total")

def calculate_order_total(order):
    TAX_RATE = 0.08
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * TAX_RATE
    return subtotal + tax

def save_order(order):
    db.save(order)
```

---

### 2. Replace Conditionals with Strategy Pattern

**Trigger**: Nested conditionals > 3 levels

```python
# Before
def calculate_shipping(order_type, weight):
    if order_type == "standard":
        return weight * 0.5
    elif order_type == "express":
        return weight * 1.5
    elif order_type == "overnight":
        return weight * 3.0

# After
class ShippingStrategy:
    def calculate(self, weight): pass

class StandardShipping(ShippingStrategy):
    def calculate(self, weight):
        return weight * 0.5

class ExpressShipping(ShippingStrategy):
    def calculate(self, weight):
        return weight * 1.5

class OvernightShipping(ShippingStrategy):
    def calculate(self, weight):
        return weight * 3.0

SHIPPING_STRATEGIES = {
    "standard": StandardShipping(),
    "express": ExpressShipping(),
    "overnight": OvernightShipping()
}

def calculate_shipping(order_type, weight):
    strategy = SHIPPING_STRATEGIES.get(order_type)
    if not strategy:
        raise ValueError(f"Unknown shipping type: {order_type}")
    return strategy.calculate(weight)
```

---

### 3. Extract Magic Numbers

**Trigger**: Hardcoded numbers in logic

```python
# Before
def calculate_discount(total):
    if total > 100:
        return total * 0.1
    return 0

# After
DISCOUNT_THRESHOLD = 100
DISCOUNT_RATE = 0.1

def calculate_discount(total):
    if total > DISCOUNT_THRESHOLD:
        return total * DISCOUNT_RATE
    return 0
```

---

## C. Performance Optimization

### 1. Database Optimization

**A. Query Optimization Checklist**

- ✅ Use indexes for WHERE, JOIN, ORDER BY columns
- ✅ Avoid SELECT \*, specify needed columns
- ✅ Use EXPLAIN ANALYZE to identify slow queries
- ✅ Batch inserts/updates (use bulk operations)
- ✅ Use connection pooling

**B. N+1 Query Prevention**

```python
# Bad: N+1 queries
orders = db.query(Order).all()
for order in orders:
    customer = db.query(Customer).filter_by(id=order.customer_id).first()
    print(f"{customer.name}: {order.total}")

# Good: Eager loading
orders = db.query(Order).options(joinedload(Order.customer)).all()
for order in orders:
    print(f"{order.customer.name}: {order.total}")
```

**C. Caching Strategy**

```python
from functools import lru_cache
import redis

# In-memory cache for pure functions
@lru_cache(maxsize=1000)
def expensive_calculation(n: int) -> int:
    return sum(i**2 for i in range(n))

# Redis cache for API responses
redis_client = redis.Redis(host='localhost', port=6379)

async def get_user(user_id: int):
    cache_key = f"user:{user_id}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    user = await db.query(User).filter_by(id=user_id).first()
    redis_client.setex(cache_key, 3600, json.dumps(user.to_dict()))
    return user
```

---

### 2. Frontend Optimization

**A. React Performance Patterns**

```typescript
import React, { memo, useMemo, useCallback } from 'react';

// Memoize expensive components
export const ExpensiveComponent = memo(({ data }) => {
  return <div>{data.map(item => <Item key={item.id} {...item} />)}</div>;
});

// Memoize expensive calculations
export const DataProcessor = ({ items }) => {
  const processedData = useMemo(() => {
    return items.map(item => expensiveTransform(item));
  }, [items]);

  return <div>{processedData}</div>;
};

// Memoize callbacks
export const ParentComponent = () => {
  const handleClick = useCallback((id: number) => {
    console.log(`Clicked ${id}`);
  }, []);

  return <ChildComponent onClick={handleClick} />;
};
```

---

## D. Debugging Strategies

### 1. Systematic Debugging Approach

**A. 5-Step Process**

1. Reproduce the issue consistently
2. Isolate the problem (binary search through code)
3. Form hypothesis about root cause
4. Test hypothesis with minimal changes
5. Verify fix doesn't break other functionality

**B. Logging Strategy**

```python
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_execution(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(f"Executing {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = await func(*args, **kwargs)
            logger.info(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}", exc_info=True)
            raise
    return wrapper

@log_execution
async def process_payment(order_id: int, amount: float):
    # Implementation
    pass
```

**C. Error Context Pattern**

```python
class PaymentError(Exception):
    def __init__(self, message: str, order_id: int, amount: float, provider: str):
        self.message = message
        self.order_id = order_id
        self.amount = amount
        self.provider = provider
        super().__init__(self.message)

    def to_dict(self):
        return {
            "error": self.message,
            "order_id": self.order_id,
            "amount": self.amount,
            "provider": self.provider
        }

try:
    process_payment(order_id, amount, provider)
except PaymentError as e:
    logger.error(f"Payment failed: {e.to_dict()}")
    # Handle error with full context
```

---

### 2. Common Bug Patterns

**A. Race Conditions**

```python
# Bad: Race condition
counter = 0

async def increment():
    global counter
    temp = counter
    await asyncio.sleep(0.001)
    counter = temp + 1

# Good: Thread-safe
import asyncio

counter_lock = asyncio.Lock()
counter = 0

async def increment():
    global counter
    async with counter_lock:
        counter += 1
```

**B. Memory Leaks**

```python
# Bad: Memory leak (event listeners not removed)
class DataProcessor:
    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)

# Good: Cleanup
class DataProcessor:
    def __init__(self):
        self.listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)

    def remove_listener(self, listener):
        self.listeners.remove(listener)

    def __del__(self):
        self.listeners.clear()
```

---

## E. API Design Standards

### 1. RESTful Conventions

```
GET    /api/v1/resources          # List resources
GET    /api/v1/resources/{id}     # Get single resource
POST   /api/v1/resources          # Create resource
PUT    /api/v1/resources/{id}     # Update resource (full)
PATCH  /api/v1/resources/{id}     # Update resource (partial)
DELETE /api/v1/resources/{id}     # Delete resource
```

### 2. Response Format

**Success Response**

```json
{
  "data": {
    "id": 123,
    "name": "Resource Name",
    "created_at": "2025-11-07T10:00:00Z"
  },
  "meta": {
    "timestamp": "2025-11-07T10:00:01Z",
    "version": "1.0.0"
  }
}
```

**Error Response**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "issue": "Invalid email format"
      }
    ]
  },
  "meta": {
    "timestamp": "2025-11-07T10:00:01Z",
    "request_id": "abc-123-def"
  }
}
```

---

## F. Production Checklist

### Before Deployment

**Code Quality**

- ✅ All functions have type hints
- ✅ All functions have docstrings
- ✅ All external calls have error handling
- ✅ All external calls have timeout and retry logic
- ✅ No console.log or print statements
- ✅ No placeholder comments

**Performance**

- ✅ Database queries use indexes
- ✅ No N+1 query patterns
- ✅ Caching implemented where appropriate
- ✅ Connection pooling configured

**Security**

- ✅ All secrets in environment variables
- ✅ All user inputs sanitized
- ✅ Parameterized queries (no SQL injection)
- ✅ CORS configured properly
- ✅ HTTPS only

**Testing**

- ✅ Unit tests passing
- ✅ Integration tests passing
- ✅ Edge cases covered
- ✅ Error conditions tested

---

## G. Quick Reference

### Refactoring Triggers

- Function > 50 lines → Extract function
- Duplicate code in 3+ places → Create reusable function
- Nested conditionals > 3 levels → Strategy pattern or early returns
- Magic numbers → Extract to constants
- Long parameter lists (>4 params) → Use objects/dataclasses

### Performance Red Flags

- SELECT \* queries
- Missing indexes on foreign keys
- N+1 query patterns
- No connection pooling
- No caching for expensive operations
- Memory leaks (unclosed connections, unremoved listeners)

### Security Red Flags

- Hardcoded credentials
- Unsanitized user inputs
- String concatenation in SQL queries
- Missing CORS configuration
- HTTP instead of HTTPS
- Plain text passwords

---

**Last Updated**: 2025-11-07
**Source**: CursorPreferencePack.md
**Confidence**: 0.95
