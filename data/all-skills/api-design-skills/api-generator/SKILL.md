---
name: api-generator
description: >
  Generate REST and GraphQL APIs from specifications, code analysis, or OpenAPI definitions.
  This skill creates production-ready API code with best practices.
version: "1.0.0"
tags: [api, rest, graphql, openapi, code-generation, express, fastify, openclaw]
metadata:
  author: "@smouj"
  category: coding
  expertise: expert
  repo: https://github.com/smouj/api-generator-skill
  license: MIT
triggers:
  - api
  - rest api
  - graphql
  - openapi
  - endpoint
  - api generation
  - create api
  - generate endpoints
---

# API Generator

You are an expert in API design and code generation.

## When to Use This Skill

- **Use when:** Generating REST or GraphQL APIs
- **Use when:** Creating OpenAPI specifications
- **Use when:** Building API endpoints from specs
- **Use when:** Implementing API authentication
- **Use when:** Setting up API validation
- **NOT for:** API documentation (use api-docs)

## Work Process

### 1. Spec
- Define API specification (OpenAPI 3.0 or GraphQL schema)
- List resources and endpoints
- Define request/response schemas
- Plan authentication and authorization

### 2. Scaffold
- Generate project structure
- Create base configuration
- Set up middleware
- Configure database connections

### 3. Implement
- Generate endpoint handlers
- Add request validation
- Implement authentication
- Create error handlers

### 4. Validate
- Test all endpoints
- Verify OpenAPI compliance
- Check error handling
- Document API usage

## Golden Rules

1. **RESTful** - Follow REST conventions and HTTP methods
2. **Version** - Always version APIs (/v1, /v2)
3. **Error handling** - Consistent error format
4. **Authentication** - Secure by default (JWT, OAuth2)
5. **Validation** - Validate all inputs

## Supported Frameworks

| Type | Framework | Language |
|------|-----------|----------|
| REST | Express, Fastify, Hono | JavaScript/TypeScript |
| REST | FastAPI, Flask | Python |
| REST | Gin, Echo | Go |
| GraphQL | Apollo, Yoga | JavaScript/TypeScript |

## Output Format

```markdown
## API Generation Report

### Generated Structure
```
src/
├── routes/
│   ├── users.ts
│   ├── products.ts
│   └── orders.ts
├── controllers/
│   ├── users.controller.ts
│   └── products.controller.ts
├── middleware/
│   ├── auth.ts
│   ├── validation.ts
│   └── errorHandler.ts
├── models/
│   ├── user.model.ts
│   └── product.model.ts
└── index.ts
```

### Generated Users Endpoint
```typescript
// GET /api/v1/users
router.get('/users', async (req, res) => {
  const { page = 1, limit = 20 } = req.query;
  const users = await User.find()
    .limit(Number(limit))
    .skip((Number(page) - 1) * Number(limit));
  
  res.json({
    data: users,
    pagination: { page, limit, total }
  });
});

// POST /api/v1/users
router.post('/users', validate(userSchema), async (req, res) => {
  const user = await User.create(req.body);
  res.status(201).json(user);
});
```

### OpenAPI Specification
```yaml
/users:
  get:
    summary: List users
    parameters:
      - name: page
        in: query
        schema:
          type: integer
          default: 1
    responses:
      '200':
        description: List of users
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: '#/components/schemas/User'
```

## Endpoints Generated
| Method | Path | Handler |
|--------|------|---------|
| GET | /api/v1/users | listUsers |
| POST | /api/v1/users | createUser |
| GET | /api/v1/users/:id | getUser |
| PUT | /api/v1/users/:id | updateUser |
| DELETE | /api/v1/users/:id | deleteUser |

## Next Steps
- [ ] Add authentication (JWT)
- [ ] Implement rate limiting
- [ ] Add API versioning
- [ ] Set up OpenAPI docs
```
