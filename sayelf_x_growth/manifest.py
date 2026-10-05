from sayelf_agent_ops.models import RoleContract, SkillContract
from sayelf_agent_ops.packs import IndustryPack

KINDS = ('BUILD','DEMO','FAILURE','INSIGHT','HUMAN','QUOTE','THREAD')
CAPABILITIES = (
    'x.signal.ingest','x.opportunity.evaluate',
    *(f'x.content.{k.lower()}' for k in KINDS),
    'x.evidence.validate','x.quality.score','x.publish.draft',
    'x.publish.schedule','x.publish.execute','x.analytics.collect',
    'x.learning.evaluate','x.conversation.recommend',
)
FORBIDDEN = ('x.reply.auto','x.dm.auto','x.like.auto','x.follow.auto',
             'x.trend.auto_publish','x.browser.write')
MANIFEST = {'id':'sayelf-agent-x-growth','version':'0.3.0','autonomy':'L2',
            'max_recommended_posts':2,'write_connector':'official-x-api',
            'human_decisions':['APPROVE','EDIT','REJECT','HOLD'],
            'forbidden':FORBIDDEN,'platform_intelligence':'contract-only'}


def register(registry):
    role = RoleContract('x.growth-operator','x','X Growth Operator',
                        'Evidence-backed X preparation and human-approved publication',
                        ('DailyRun','Draft','Learning'), CAPABILITIES,FORBIDDEN)
    skills = tuple(SkillContract(id,role.id,id,('X_SIGNAL',),('local-domain-result',),
                                validation=('hard-gates','L2'),status='experimental')
                   for id in CAPABILITIES)
    registry.register_pack(IndustryPack('sayelf-x-v03','x',(role,),skills,()))
    registry.activate_role(role.id)
    return registry
