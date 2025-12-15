# PRD: Transaction Alerts

## Problem Statement
Users don't know when suspicious activity happens on their account until they check manually. This leads to delayed fraud detection and poor user trust.

## Goals
1. Notify users within 30 seconds of suspicious transaction
2. Support push, SMS, and email channels
3. Let users configure alert thresholds
4. Reduce fraud losses by 40%

## User Stories
- As a user, I want to receive instant alerts when a transaction over $500 occurs
- As a user, I want to customize which transactions trigger alerts
- As a user, I want to snooze alerts temporarily when traveling

## Success Metrics
- Alert delivery latency < 30 seconds (p99)
- User opt-in rate > 60%
- False positive rate < 5%

## Constraints
- Must integrate with existing notification service
- Cannot store transaction data longer than 90 days
- Must support 10M users with 100M transactions/day
