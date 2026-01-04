# AI Assistant Working Guidelines for Marketplace Project

## Project Context
You are working on a **Latvian Marketplace Platform** with two main features:
1. **Buy/Sell Classifieds** - Users can list items for sale
2. **Quick Help Tasks** - Location-based service requests with interactive map

### Repository Structure
- **Backend**: Flask API (Python) with PostgreSQL, Redis, JWT auth, Stripe payments
- **Frontend**: React + TypeScript with mobile-first design and Leaflet maps

## Your Role & Autonomy

### Work Independently On:
- Code reviews and suggestions
- Bug fixes in existing code
- Documentation improvements
- Test writing and enhancement
- Code refactoring for better practices
- Performance optimizations
- Security improvements
- Dependency updates (minor versions)

### Always Ask Permission Before:
- Creating new database migrations
- Modifying database schema
- Adding new major dependencies
- Changing API endpoints or contracts
- Modifying authentication/authorization logic
- Altering payment processing code
- Making breaking changes to existing features
- Deploying to production
- Modifying environment variables or configuration
- Major architectural changes

## Working Process

1. **Analyze First**: Always examine the existing code structure before making changes
2. **Follow Patterns**: Match the coding style and patterns already in use
3. **Test Your Changes**: Write or update tests for any code modifications
4. **Document**: Update relevant documentation for significant changes
5. **Security First**: Never expose secrets, always validate input, follow security best practices
6. **Ask Clarifying Questions**: If requirements are unclear, ask before proceeding

## Key Technical Details

### Backend (marketplace-backend)
- **Language**: Python 3.x
- **Framework**: Flask
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis
- **Auth**: JWT tokens
- **Payments**: Stripe integration
- **Testing**: pytest
- **API Style**: RESTful

### Frontend (marketplace-frontend)
- **Language**: TypeScript
- **Framework**: React
- **Maps**: Leaflet for geographic features
- **Responsive**: Mobile-first approach

### Code Style Guidelines
- Follow PEP 8 for Python (backend)
- Use ESLint/Prettier standards for TypeScript (frontend)
- Write clear, self-documenting code with comments for complex logic
- Keep functions small and focused
- Use meaningful variable and function names

## Communication Protocol

### When Making Changes:
```
I'm going to [action] by [approach]. This will [impact].
[Show code snippet or explanation]
Should I proceed?
```

### When Uncertain:
```
I found [situation]. I could approach this by:
1. Option A: [description]
2. Option B: [description]
Which approach would you prefer?
```

### After Completing Work:
```
Completed: [task description]
Changes made:
- [change 1]
- [change 2]

Files modified: [list]
Tests: [status]
```

## Current Project Status
Refer to `PROJECT_STATUS.md` for detailed information about implemented features, pending work, and known issues.

## Security Reminders
- Never commit API keys, secrets, or credentials
- Validate all user input
- Use parameterized queries to prevent SQL injection
- Implement proper CORS policies
- Keep dependencies updated
- Follow OWASP security guidelines

## Testing Requirements
- Write unit tests for new business logic
- Integration tests for API endpoints
- Maintain >80% code coverage target
- Test edge cases and error conditions

## Documentation Standards
- Update README.md for setup changes
- API changes require endpoint documentation
- Complex algorithms need inline explanation
- Keep PROJECT_STATUS.md current

---

**Remember**: You're a collaborator, not just a code generator. Think critically, ask questions, and prioritize code quality, security, and maintainability.