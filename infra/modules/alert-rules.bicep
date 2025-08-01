param location string
param tags object
param containerAppName string

// Container Appリソースの参照
resource containerApp 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: containerAppName
}

// 5xx系ステータスコードアラートルール
resource alert5xxStatusCodes 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${containerAppName}-5xx-alerts'
  location: 'global'
  tags: tags
  properties: {
    description: 'Alert when 5xx errors exceed threshold'
    severity: 2
    enabled: true
    scopes: [
      containerApp.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HTTP5xxErrors'
          metricName: 'Requests'
          metricNamespace: 'Microsoft.App/containerApps'
          dimensions: [
            {
              name: 'statusCodeCategory'
              operator: 'Include'
              values: ['5xx']
            }
          ]
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    autoMitigate: true
    targetResourceType: 'Microsoft.App/containerApps'
    targetResourceRegion: location
  }
}

// 応答時間アラートルール
resource alertResponseTime 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${containerAppName}-response-time-alerts'
  location: 'global'
  tags: tags
  properties: {
    description: 'Alert when average response time exceeds 5 seconds'
    severity: 2
    enabled: true
    scopes: [
      containerApp.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighResponseTime'
          metricName: 'ResponseTime'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 5000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    autoMitigate: true
    targetResourceType: 'Microsoft.App/containerApps'
    targetResourceRegion: location
  }
}

output alert5xxId string = alert5xxStatusCodes.id
output alertResponseTimeId string = alertResponseTime.id
