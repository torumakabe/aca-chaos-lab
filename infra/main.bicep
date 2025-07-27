targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

module managedIdentity './modules/managed-identity.bicep' = {
  name: 'managed-identity'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    managedIdentityName: '${abbrs.managedIdentityUserAssignedIdentities}${resourceToken}'
  }
}

module monitoring './modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
  }
}

module network './modules/network.bicep' = {
  name: 'network'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    vnetName: '${abbrs.networkVirtualNetworks}${resourceToken}'
  }
}

module redis './modules/redis.bicep' = {
  name: 'redis'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    redisName: '${abbrs.cacheRedis}${resourceToken}'
    vnetId: network.outputs.vnetId
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    containerAppPrincipalId: managedIdentity.outputs.managedIdentityPrincipalId
  }
}

module containerRegistry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    registryName: '${abbrs.containerRegistryRegistries}${resourceToken}'
    vnetId: network.outputs.vnetId
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    managedIdentityPrincipalId: managedIdentity.outputs.managedIdentityPrincipalId
  }
}

module containerAppsEnvironment './modules/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    environmentName: '${abbrs.appManagedEnvironments}${resourceToken}'
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsWorkspaceName
    containerAppsSubnetId: network.outputs.containerAppsSubnetId
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'container-app'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    containerAppName: '${abbrs.appContainerApps}app-${resourceToken}'
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.environmentName
    containerImage: '${containerRegistry.outputs.loginServer}/chaos-lab-app:latest'
    redisHost: redis.outputs.redisHost
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    managedIdentityName: managedIdentity.outputs.managedIdentityName
    managedIdentityClientId: managedIdentity.outputs.managedIdentityClientId
  }
}

// Container App's managed identity is automatically assigned the default access policy for Redis Enterprise database

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_CONTAINER_APP_NAME string = containerApp.outputs.containerAppName
output AZURE_CONTAINER_APP_URI string = containerApp.outputs.containerAppUri
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.outputs.managedIdentityClientId
output AZURE_REDIS_HOST string = redis.outputs.redisHost
output AZURE_REDIS_PORT int = redis.outputs.redisPort
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.registryName
output AZURE_CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.outputs.loginServer
@secure()
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString