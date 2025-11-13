@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('Container Registry login server')
param containerRegistryLoginServer string

@description('Managed Identity resource ID')
param managedIdentityId string

@description('Managed Identity client ID')
param managedIdentityClientId string

@description('Application Insights name')
param applicationInsightsName string

@description('Redis host')
param redisHost string

@description('The image name for the container')
param imageName string

var abbrs = loadJsonContent('../abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  'azd-service-name': 'app'
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

module containerApp 'br/public:avm/res/app/container-app:0.17.0' = {
  name: 'container-app'
  params: {
    name: '${abbrs.appContainerApps}app-${resourceToken}'
    location: location
    tags: tags
    environmentResourceId: containerAppsEnvironmentId
    managedIdentities: {
      userAssignedResourceIds: [managedIdentityId]
    }
    registries: [
      {
        server: containerRegistryLoginServer
        identity: managedIdentityId
      }
    ]
    containers: [
      {
        name: 'main'
        image: imageName
        resources: {
          cpu: json('0.25')
          memory: '0.5Gi'
        }
        probes: [
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
        env: [
          {
            name: 'REDIS_HOST'
            value: redisHost
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
            value: managedIdentityClientId
          }
        ]
      }
    ]
    secrets: [
      {
        name: 'appinsights-connection-string'
        value: applicationInsights.properties.ConnectionString
      }
    ]
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 1
    }
    ingressTargetPort: 8000
    ingressExternal: true
  }
}

module alertRules './alert-rules.bicep' = {
  name: 'alert-rules'
  params: {
    location: location
    tags: tags
    containerAppName: containerApp.outputs.name
  }
}

output name string = containerApp.outputs.name
output fqdn string = containerApp.outputs.fqdn
output alert5xxId string = alertRules.outputs.alert5xxId
output alertResponseTimeId string = alertRules.outputs.alertResponseTimeId
