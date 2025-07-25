param location string
param tags object
param redisName string
param vnetId string
param privateEndpointSubnetId string
param principalId string
param containerAppPrincipalId string = ''

resource redisEnterprise 'Microsoft.Cache/redisEnterprise@2024-10-01' = {
  name: redisName
  location: location
  tags: tags
  sku: {
    name: 'Balanced_B0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    minimumTlsVersion: '1.2'    
  }
}

resource redisEnterpriseDatabase 'Microsoft.Cache/redisEnterprise/databases@2024-10-01' = {
  name: 'default'
  parent: redisEnterprise
  properties:{
    clientProtocol: 'Encrypted'
    port: 10000
    clusteringPolicy: 'OSSCluster'
    evictionPolicy: 'NoEviction'
    persistence:{
      aofEnabled: false 
      rdbEnabled: false
    }
  }
}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.redisenterprise.cache.azure.net'
  location: 'global'
  tags: tags
}

resource privateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: '${redisName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = {
  name: '${redisName}-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${redisName}-connection'
        properties: {
          privateLinkServiceId: redisEnterprise.id
          groupIds: [
            'redisEnterprise'
          ]
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-05-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'redis-config'
        properties: {
          privateDnsZoneId: privateDnsZone.id
        }
      }
    ]
  }
}

// Redis Enterprise Contributor ロールをプリンシパルに割り当て（開発者アクセス用）
resource redisContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  name: guid(redisEnterprise.id, principalId, 'f7f8cfd5-57b3-4a05-b8a5-26a1aa2cf7c5')
  scope: redisEnterprise
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'f7f8cfd5-57b3-4a05-b8a5-26a1aa2cf7c5')
    principalId: principalId
  }
}

// Container AppのManaged Identityにデータベースアクセスポリシーを割り当て
resource accessPolicyAssignmentForApp 'Microsoft.Cache/redisEnterprise/databases/accessPolicyAssignments@2024-10-01' = if (!empty(containerAppPrincipalId)) {
  parent: redisEnterpriseDatabase
  name: 'container-app-assignment'
  properties: {
    accessPolicyName: 'default'
    user: {
      objectId: containerAppPrincipalId
    }
  }
}

output redisId string = redisEnterprise.id
output redisHost string = redisEnterprise.properties.hostName
output redisPort int = 10000