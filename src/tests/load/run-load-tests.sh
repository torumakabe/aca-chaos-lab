#!/bin/bash
set -euo pipefail

# Script to run various load test scenarios
# Usage: ./run-load-tests.sh <host> <scenario>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <host> <scenario>"
    echo "  host: Target host (e.g., https://myapp.azurecontainerapps.io)"
    echo "  scenario: Test scenario (baseline|stress|spike|chaos)"
    exit 1
fi

HOST="$1"
SCENARIO="$2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure we're in the right directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create results directory
RESULTS_DIR="results/$(date +%Y%m%d_%H%M%S)_${SCENARIO}"
mkdir -p "$RESULTS_DIR"

echo -e "${BLUE}🚀 Running load test scenario: $SCENARIO${NC}"
echo "Target host: $HOST"
echo "Results will be saved to: $RESULTS_DIR"

case "$SCENARIO" in
    "baseline")
        echo -e "${YELLOW}📊 Running baseline performance test...${NC}"
        echo "Configuration: 10 users, 5 minutes"
        
        locust \
            --locustfile locustfile.py \
            --host "$HOST" \
            --users 10 \
            --spawn-rate 2 \
            --run-time 5m \
            --headless \
            --html "$RESULTS_DIR/baseline_report.html" \
            --csv "$RESULTS_DIR/baseline" \
            SteadyLoadUser
        ;;
    
    "stress")
        echo -e "${YELLOW}💪 Running stress test...${NC}"
        echo "Configuration: Ramping up to 300 users over 15 minutes"
        
        locust \
            --locustfile scenarios/stress.py \
            --host "$HOST" \
            --headless \
            --html "$RESULTS_DIR/stress_report.html" \
            --csv "$RESULTS_DIR/stress"
        ;;
    
    "spike")
        echo -e "${YELLOW}⚡ Running spike test...${NC}"
        echo "Configuration: 100 users spawned at 50/second"
        
        locust \
            --locustfile locustfile.py \
            --host "$HOST" \
            --users 100 \
            --spawn-rate 50 \
            --run-time 3m \
            --headless \
            --html "$RESULTS_DIR/spike_report.html" \
            --csv "$RESULTS_DIR/spike" \
            SpikeTestUser
        ;;
    
    "chaos")
        echo -e "${YELLOW}🔥 Running chaos test...${NC}"
        echo "Configuration: 50 users with chaos injection"
        echo -e "${RED}WARNING: This test will inject failures!${NC}"
        
        # Confirm before running chaos test
        read -p "Are you sure you want to run chaos testing? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Chaos test cancelled"
            exit 0
        fi
        
        locust \
            --locustfile locustfile.py \
            --host "$HOST" \
            --users 50 \
            --spawn-rate 5 \
            --run-time 10m \
            --headless \
            --html "$RESULTS_DIR/chaos_report.html" \
            --csv "$RESULTS_DIR/chaos" \
            ChaosTestUser
        ;;
    
    *)
        echo -e "${RED}❌ Unknown scenario: $SCENARIO${NC}"
        echo "Valid scenarios: baseline, stress, spike, chaos"
        exit 1
        ;;
esac

echo -e "${GREEN}✅ Load test completed!${NC}"
echo "Results saved to: $RESULTS_DIR"

# Generate summary report
echo -e "${BLUE}📈 Generating summary report...${NC}"
cat > "$RESULTS_DIR/summary.txt" << EOF
Load Test Summary
=================
Date: $(date)
Scenario: $SCENARIO
Target: $HOST

Key Metrics:
EOF

# Extract key metrics from CSV files
if [ -f "$RESULTS_DIR/${SCENARIO}_stats.csv" ]; then
    echo "- Request Statistics:" >> "$RESULTS_DIR/summary.txt"
    tail -n 1 "$RESULTS_DIR/${SCENARIO}_stats.csv" | awk -F',' '{
        print "  - Total Requests: " $3
        print "  - Failure Rate: " $9 "%"
        print "  - Avg Response Time: " $6 "ms"
        print "  - Max Response Time: " $8 "ms"
    }' >> "$RESULTS_DIR/summary.txt"
fi

echo -e "${GREEN}Summary report generated: $RESULTS_DIR/summary.txt${NC}"

# Open HTML report if on a system with a browser
if command -v open &> /dev/null; then
    open "$RESULTS_DIR/${SCENARIO}_report.html"
elif command -v xdg-open &> /dev/null; then
    xdg-open "$RESULTS_DIR/${SCENARIO}_report.html"
fi