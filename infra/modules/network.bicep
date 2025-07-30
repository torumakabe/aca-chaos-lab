param location string
param tags object
param vnetName string

var vnetAddressPrefix = '10.0.0.0/16'
var containerAppsSubnetPrefix = '10.0.1.0/24'
var privateEndpointSubnetPrefix = '10.0.2.0/24'

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-05-01' = {
  name: 'nsg-${vnetName}-chaos'
  location: location
  tags: tags
  properties: {
    securityRules: []
    // デフォルトルールで送信は許可される
    // Redis障害注入時に送信拒否ルールを動的に追加
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-05-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'containerApps'
        properties: {
          addressPrefix: containerAppsSubnetPrefix
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'privateEndpoints'
        properties: {
          addressPrefix: privateEndpointSubnetPrefix
          privateEndpointNetworkPolicies: 'Enabled'
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output containerAppsSubnetId string = vnet.properties.subnets[0].id
output privateEndpointSubnetId string = vnet.properties.subnets[1].id
output nsgId string = nsg.id
output nsgName string = nsg.name
