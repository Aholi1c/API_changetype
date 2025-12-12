# API Change Types Documentation

This document explains the meaning of different `change_type` values found in the preprocessed API change data across various programming languages and libraries.

## Most Common Change Types

### 1. API Deprecation
**Occurrences**: 1,036 (36.8% of all changes)

Indicates that an API is officially deprecated and may be removed in a future version. The API may still work but its use is discouraged.

**Example**:
```json
{
  "api": "reflect.PtrTo",
  "package": "Go",
  "change_type": "API Deprecation",
  "reason": "Deprecated in favor of PointerTo"
}
```

### 2. API Documentation
**Occurrences**: 638 (22.7%)

Represents documentation updates or clarifications. The API functionality may not have changed, but its documentation was improved or corrected.

**Example**:
```json
{
  "api": "animateChild",
  "package": "Angular",
  "change_type": "API Documentation",
  "reason": "Documentation updates for animation lifecycle hooks"
}
```

### 3. Behavior Change
**Occurrences**: 381 (13.5%)

The API's behavior has changed in a potentially backward-incompatible way. The signature might be the same, but the function behaves differently.

**Example**:
```json
{
  "api": "reflect.Value.IsZero",
  "package": "Go",
  "change_type": "Behavior Change",
  "reason": "Now handles negative zero consistently across platforms"
}
```

### 4. Parameter Change
**Occurrences**: 192 (6.8%)

Changes to function/method parameters, including:
- Addition/removal of parameters
- Parameter type changes
- Parameter name changes
- Default value changes

**Example**:
```json
{
  "api": "Regexp::new",
  "package": "Ruby",
  "change_type": "Parameter Change",
  "reason": "Reduced from 3 to 2 arguments for simplification"
}
```

### 5. API Removal
**Occurrences**: 141 (5.0%)

The API has been completely removed and is no longer available for use.

**Example**:
```json
{
  "api": "Fixnum",
  "package": "Ruby",
  "change_type": "API Removal",
  "reason": "Unified with Bignum into Integer class in Ruby 3.2.0"
}
```

## Other Important Change Types

### 6. API Usage Discouraged
The API is not officially deprecated but its use is discouraged for various reasons such as performance issues, better alternatives, or potential future deprecation.

**Example**:
```json
{
  "api": "numpy.ndarray.shape",
  "package": "NumPy",
  "change_type": "API Usage Discouraged",
  "reason": "Setting arr.shape is discouraged, use ndarray.reshape instead"
}
```

### 7. Method Deprecation
Specific to individual methods within a class or interface.

**Example**:
```json
{
  "api": "finalize",
  "package": "Java",
  "change_type": "Method Deprecation",
  "reason": "Finalization mechanism is deprecated"
}
```

### 8. Performance Optimization
Improvements to the performance characteristics of an API without changing its functionality.

**Example**:
```json
{
  "api": "reflect.ValueOf",
  "package": "Go",
  "change_type": "Performance Optimization",
  "reason": "No longer forces heap allocation in some cases"
}
```

### 9. API Addition
Introduction of new APIs to the library or framework.

**Example**:
```json
{
  "api": "Nokogiri::HTML4",
  "package": "Nokogiri",
  "change_type": "API Addition",
  "reason": "New namespace for HTML4-specific functionality"
}
```

## Granular Change Types

### Class/Interface/Package Deprecation
- **Class Deprecation**: Entire classes marked as deprecated
- **Interface Deprecation**: Interfaces deprecated, often with replacement interfaces
- **Package Deprecation**: Whole packages deprecated for reorganization

### Constructor/Function Deprecation
- **Constructor Deprecation**: Specific constructors deprecated
- **Function Deprecation**: Standalone functions deprecated

### Setting/Configuration Deprecation
- **Setting Deprecation**: Configuration settings deprecated
- **Configuration Removal**: Settings completely removed

### Security-Related Changes
- **Security Enhancement**: Security improvements to APIs
- **Security Deprecation**: Features deprecated due to security concerns

## Behavioral Subcategories

### Error Handling Changes
Modifications in how errors are raised, caught, or reported.

### Thread Safety Changes
Changes related to concurrency and thread safety guarantees.

### Memory Management Changes
Modifications to how memory is allocated, managed, or freed.

## Special Cases

### None/No Change
138 entries have no specified change type, often indicating:
- Missing data
- Minor changes not categorized
- Unspecified changes

### Compound Change Types
Some entries use compound labels like:
- "API Deprecation / Default Change"
- "Behavior Change / Performance Improvement"

## Categorization Patterns by Language

### Python Libraries
- Favor "API Usage Discouraged" for style improvements
- Common "Setting Deprecation" for configuration changes

### Java Ecosystem
- Granular deprecation types (Constructor, Interface, Package)
- Strong emphasis on security-related deprecations

### Go/Rust
- Prefer "API Deprecation" and "Behavior Change"
- Focus on performance and memory safety improvements

### JavaScript/TypeScript
- Mix of "API Deprecation" and "Breaking Change"
- Emphasis on modernization and type safety

## Impact Assessment

### Critical Changes
- **API Removal**: Requires immediate code changes
- **Breaking Change**: Will break existing implementations
- **Behavior Change**: May cause subtle bugs

### Advisory Changes
- **API Deprecation**: Plan migration but not urgent
- **API Usage Discouraged**: Consider alternatives for new code

### Informational
- **API Documentation**: No code changes needed
- **Performance Optimization**: Benefits are automatic

## Best Practices

1. **Monitor Deprecations**: Act on deprecation warnings before removal
2. **Test Behavior Changes**: Verify functionality remains correct
3. **Review Documentation**: Stay informed about API changes
4. **Plan Migrations**: Schedule updates for deprecated APIs
5. **Consider Alternatives**: Evaluate discouraged APIs for better options

## Conclusion

The data shows that software libraries evolve continuously, with deprecation being the most common type of change. Understanding these change types helps developers maintain their codebase effectively and plan for future updates.