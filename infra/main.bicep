targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('The image name for the app service')
param containerAppImageName string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Principal ID of the user running deployment (for ACR push access)')
param principalId string = ''

@description('Specifies if the container app already exists')
param containerAppExists bool = false

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
    currentUserPrincipalId: principalId
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

module containerApp 'br/public:avm/ptn/azd/container-app-upsert:0.2.0' = {
  name: 'container-app'
  scope: resourceGroup
  params: {
    name: '${abbrs.appContainerApps}app-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'app' })
    containerAppsEnvironmentName: containerAppsEnvironment.outputs.environmentName
    containerRegistryName: containerRegistry.outputs.registryName
    imageName: !empty(containerAppImageName) ? containerAppImageName : ''
    exists: containerAppExists
    identityType: 'UserAssigned'
    identityName: managedIdentity.outputs.managedIdentityName
    identityPrincipalId: managedIdentity.outputs.managedIdentityPrincipalId
    userAssignedIdentityResourceId: managedIdentity.outputs.managedIdentityId
    env: [
      {
        name: 'REDIS_HOST'
        value: redis.outputs.redisHost
      }
      {
        name: 'REDIS_PORT'
        value: '10000'
      }
      {
        name: 'REDIS_SSL'
        value: 'true'
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        secretRef: 'appinsights-connection-string'
      }
      {
        name: 'APP_PORT'
        value: '8000'
      }
      {
        name: 'LOG_LEVEL'
        value: 'INFO'
      }
      {
        name: 'AZURE_CLIENT_ID'
        value: managedIdentity.outputs.managedIdentityClientId
      }
    ]
    secrets: [
      {
        name: 'appinsights-connection-string'
        value: monitoring.outputs.applicationInsightsConnectionString
      }
    ]
    containerProbes: [
      {
        type: 'Liveness'
        tcpSocket: {
          port: 8000
        }
        initialDelaySeconds: 60
        periodSeconds: 10
        timeoutSeconds: 10
        failureThreshold: 5
        successThreshold: 1
      }
      {
        type: 'Readiness'
        httpGet: {
          path: '/health'
          port: 8000
          scheme: 'HTTP'
        }
        initialDelaySeconds: 10
        periodSeconds: 5
        timeoutSeconds: 3
        failureThreshold: 2
        successThreshold: 2
      }
    ]
    targetPort: 8000
    containerMinReplicas: 1
    containerMaxReplicas: 1
    containerCpuCoreCount: '0.25'
    containerMemory: '0.5Gi'
    ingressEnabled: true
    external: true
  }
}

module alertRules './modules/alert-rules.bicep' = {
  name: 'alert-rules'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    containerAppName: containerApp.outputs.name
  }
}

// Container App's managed identity is automatically assigned the default access policy for Redis Enterprise database

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup.name
output SERVICE_APP_NAME string = containerApp.outputs.name
output SERVICE_APP_URI string = containerApp.outputs.uri
output AZURE_MANAGED_IDENTITY_CLIENT_ID string = managedIdentity.outputs.managedIdentityClientId
output AZURE_REDIS_HOST string = redis.outputs.redisHost
output AZURE_REDIS_PORT int = redis.outputs.redisPort
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.registryName
output AZURE_CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.outputs.loginServer
@secure()
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output AZURE_ALERT_5XX_ID string = alertRules.outputs.alert5xxId
output AZURE_ALERT_RESPONSE_TIME_ID string = alertRules.outputs.alertResponseTimeId
output AZURE_NSG_NAME string = network.outputs.nsgName
