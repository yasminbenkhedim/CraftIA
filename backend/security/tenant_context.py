from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel

class TenantContext(BaseModel):
    tenant_id: str
    user_id: str
    roles: List[str]
    jwt_claims: Dict

class TenantQuota(BaseModel):
    tenant_id: str
    max_concurrent_jobs: int = 10
    max_queued_jobs: int = 50
    gpu_minutes_quota: int = 600
    storage_quota_gb: float = 100.0
    daily_render_quota: int = 100
    priority_class: str = 'standard'
    used_concurrent_jobs: int = 0
    used_gpu_minutes: float = 0.0

class TenantQuotaManager:
    def __init__(self):
        self.quotas: Dict[str, TenantQuota] = {}

    def register_tenant(self, tenant_id: str, **kwargs) -> TenantQuota:
        quota = TenantQuota(tenant_id=tenant_id, **kwargs)
        self.quotas[tenant_id] = quota
        return quota

    def check_quota(self, tenant_id: str, resource_type: str) -> Tuple[bool, str]:
        quota = self.quotas.get(tenant_id)
        if not quota:
            return False, "Tenant not found"
        
        if resource_type == 'concurrent_jobs':
            if quota.used_concurrent_jobs >= quota.max_concurrent_jobs:
                return False, "Max concurrent jobs reached"
        elif resource_type == 'gpu_minutes':
            if quota.used_gpu_minutes >= quota.gpu_minutes_quota:
                return False, "GPU minutes quota reached"
        return True, "Quota OK"

    def consume_quota(self, tenant_id: str, resource_type: str, amount: float) -> bool:
        quota = self.quotas.get(tenant_id)
        if not quota:
            return False
            
        if resource_type == 'concurrent_jobs':
            quota.used_concurrent_jobs += int(amount)
        elif resource_type == 'gpu_minutes':
            quota.used_gpu_minutes += amount
        return True

    def get_tenant_stats(self, tenant_id: str) -> Dict:
        quota = self.quotas.get(tenant_id)
        if not quota:
            return {}
        return quota.model_dump()

class WeightedFairScheduler:
    def __init__(self):
        self.tenant_weights: Dict[str, float] = {}
        self.pending_counts: Dict[str, int] = {}
        self.served_counts: Dict[str, int] = {}

    def set_weight(self, tenant_id: str, weight: float):
        self.tenant_weights[tenant_id] = weight
        if tenant_id not in self.served_counts:
            self.served_counts[tenant_id] = 0
        if tenant_id not in self.pending_counts:
            self.pending_counts[tenant_id] = 0

    def select_next_tenant(self, candidates: List[str]) -> str:
        if not candidates:
            return ""
        
        best_tenant = None
        min_ratio = float('inf')
        
        for tenant_id in candidates:
            weight = self.tenant_weights.get(tenant_id, 1.0)
            served = self.served_counts.get(tenant_id, 0)
            ratio = served / weight if weight > 0 else float('inf')
            
            if ratio < min_ratio:
                min_ratio = ratio
                best_tenant = tenant_id
                
        return best_tenant

    def record_served(self, tenant_id: str):
        if tenant_id not in self.served_counts:
            self.served_counts[tenant_id] = 0
        self.served_counts[tenant_id] += 1

    def get_fairness_report(self) -> Dict:
        report = {}
        for tenant_id, served in self.served_counts.items():
            weight = self.tenant_weights.get(tenant_id, 1.0)
            report[tenant_id] = {
                'served': served,
                'weight': weight,
                'ratio': served / weight if weight > 0 else float('inf')
            }
        return report
