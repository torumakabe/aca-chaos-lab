---
description: "Infrastructure as Code with Bicep"
applyTo: "**/*.bicep"
---

## Naming Conventions

- When writing Bicep code, use lowerCamelCase for all names (variables, parameters, resources)
- Use resource type descriptive symbolic names (e.g., 'storageAccount' not 'storageAccountName')
- Avoid using 'name' in a symbolic name as it represents the resource, not the resource's name
- Avoid distinguishing variables and parameters by the use of suffixes
- Follow Azure Cloud Adoption Framework naming conventions for consistency across the organization:
  - **Resource Naming**: Use standardized naming components like `<resource-type>-<workload>-<environment>-<region>-<instance>` (e.g., `rg-aks-scale-to-zero-dev-japaneast-001`)
  - **Resource Abbreviations**: Use official Azure resource type abbreviations as defined in the [Azure resource abbreviations guide](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)
  - **Reference Documentation**: Follow the complete naming guidance from [Azure resource naming conventions](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming)
  - **Naming Components**: Include relevant components such as organization, business unit, workload, environment, region, and instance number
  - **Delimiters**: Use hyphens (-) to separate naming components for improved readability where resource supports it
  - **Scope Awareness**: Understand resource name scope requirements (global, resource group, or resource-level uniqueness)

## Structure and Declaration

- Always declare parameters at the top of files with @description decorators
- Use latest stable API versions for all resources
- Use descriptive @description decorators for all parameters
- Specify minimum and maximum character length for naming parameters

## API Versions

- Always use the latest stable (non-preview) API versions for all Azure resources
- Check Azure REST API documentation or use `az provider show` command to identify the latest stable versions
- When updating API versions, test thoroughly to ensure compatibility with existing resource configurations
- Document any specific API version requirements or constraints in comments when deviating from the latest stable version

## Parameters

- Set default values that are safe for test environments (use low-cost pricing tiers)
- Use @allowed decorator sparingly to avoid blocking valid deployments
- Use parameters for settings that change between deployments

## Variables

- Variables automatically infer type from the resolved value
- Use variables to contain complex expressions instead of embedding them directly in resource properties

## Resource References

- Use symbolic names for resource references instead of reference() or resourceId() functions
- Create resource dependencies through symbolic names (resourceA.id) not explicit dependsOn
- For accessing properties from other resources, use the 'existing' keyword instead of passing values through outputs

## Resource Names

- Use template expressions with uniqueString() to create meaningful and unique resource names
- Add prefixes to uniqueString() results since some resources don't allow names starting with numbers

## Child Resources

- Avoid excessive nesting of child resources
- Use parent property or nesting instead of constructing resource names for child resources

## Security

- Never include secrets or keys in outputs
- Use resource properties directly in outputs (e.g., storageAccount.properties.primaryEndpoints)

## Documentation

- Include helpful // comments within your Bicep files to improve readability
