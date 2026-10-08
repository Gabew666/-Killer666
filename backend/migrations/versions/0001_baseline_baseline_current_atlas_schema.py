"""Baseline current ATLAS schema

Revision ID: 0001_baseline
Revises: 
"""

from alembic import op
import sqlalchemy as sa


revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None


# Frozen snapshot: this revision deliberately does not import application models.
# Adopt current databases and upgrade only the known nullable/additive v0.1 fields.
EXPECTED_COLUMNS = {'curriculum_item_records': ['id',
                             'package_id',
                             'item_type',
                             'item_key',
                             'object_id',
                             'latest_version',
                             'content_hash',
                             'provenance'],
 'curriculum_package_records': ['id',
                                'package_id',
                                'version',
                                'content_hash',
                                'content_status',
                                'payload',
                                'imported_at'],
 'students': ['id', 'name', 'created_at'],
 'subjects': ['id', 'name'],
 'assessments': ['id', 'name', 'subject_id', 'start_date', 'end_date', 'importance'],
 'curriculum_units': ['id', 'subject_id', 'key', 'name', 'description', 'position'],
 'study_sessions': ['id',
                    'student_id',
                    'available_minutes',
                    'planned_minutes',
                    'created_at',
                    'planned_at',
                    'started_at',
                    'completed_at',
                    'used_minutes',
                    'actual_minutes',
                    'current_activity_id',
                    'strategy',
                    'adaptation_reason',
                    'status',
                    'plan_snapshot'],
 'concepts': ['id',
              'subject_id',
              'unit_id',
              'parent_concept_id',
              'slug',
              'name',
              'description',
              'difficulty',
              'importance',
              'estimated_minutes',
              'learning_objectives',
              'created_at'],
 'assessment_concepts': ['assessment_id', 'concept_id', 'weight'],
 'concept_dependencies': ['id',
                          'concept_id',
                          'prerequisite_concept_id',
                          'dependency_strength',
                          'is_essential'],
 'curriculum_explanations': ['id', 'subject_id', 'concept_id', 'key', 'text'],
 'exercises': ['id',
               'concept_id',
               'slug',
               'exercise_type',
               'prompt',
               'options',
               'answer_spec',
               'explanation',
               'difficulty',
               'origin_type',
               'provenance',
               'error_map'],
 'review_schedules': ['id', 'student_id', 'concept_id', 'stage', 'due_at', 'updated_at'],
 'student_concept_states': ['student_id',
                            'concept_id',
                            'mastery',
                            'retention',
                            'retention_calculated_at',
                            'self_confidence',
                            'evidence_confidence',
                            'evidence_count',
                            'delayed_evidence_count',
                            'stability_days',
                            'times_seen',
                            'times_attempted',
                            'times_correct',
                            'independent_correct',
                            'last_seen_at',
                            'last_attempt_at',
                            'last_correct_at',
                            'last_independent_at',
                            'difficulty_success_rate',
                            'difficulty_attempt_weight',
                            'next_review_at',
                            'status'],
 'session_activities': ['id',
                        'session_id',
                        'concept_id',
                        'exercise_id',
                        'position',
                        'block_index',
                        'activity_type',
                        'estimated_minutes',
                        'instructions',
                        'planned_at',
                        'started_at',
                        'completed_at',
                        'status',
                        'actual_minutes',
                        'strategy',
                        'executed',
                        'adaptation_reason',
                        'is_conditional',
                        'decision_after',
                        'execution_order'],
 'exercise_attempts': ['id',
                       'student_id',
                       'exercise_id',
                       'activity_id',
                       'attempt_kind',
                       'answer',
                       'correct',
                       'score',
                       'error_type',
                       'concepts_involved',
                       'evaluator_confidence',
                       'feedback',
                       'hints_used',
                       'attempt_number',
                       'response_time',
                       'self_confidence',
                       'is_independent',
                       'occurred_at'],
 'learning_events': ['id',
                     'student_id',
                     'concept_id',
                     'attempt_id',
                     'event_type',
                     'payload',
                     'occurred_at']}

ADDITIONS = {
    "exercises": {
        "origin_type": sa.Column("origin_type", sa.String(40), nullable=True),
        "provenance": sa.Column("provenance", sa.JSON(), nullable=True),
    },
    "concepts": {
        "unit_id": sa.Column("unit_id", sa.Integer(), sa.ForeignKey("curriculum_units.id"), nullable=True),
        "parent_concept_id": sa.Column("parent_concept_id", sa.Integer(), sa.ForeignKey("concepts.id"), nullable=True),
        "learning_objectives": sa.Column("learning_objectives", sa.JSON(), nullable=True),
    },
    "study_sessions": {
        "planned_at": sa.Column("planned_at", sa.DateTime(), nullable=True),
        "started_at": sa.Column("started_at", sa.DateTime(), nullable=True),
        "used_minutes": sa.Column("used_minutes", sa.Integer(), nullable=True, server_default="0"),
        "actual_minutes": sa.Column("actual_minutes", sa.Integer(), nullable=True),
        "current_activity_id": sa.Column("current_activity_id", sa.Integer(), nullable=True),
        "strategy": sa.Column("strategy", sa.String(20), nullable=True),
        "adaptation_reason": sa.Column("adaptation_reason", sa.Text(), nullable=True),
    },
    "session_activities": {
        "block_index": sa.Column("block_index", sa.Integer(), nullable=True),
        "planned_at": sa.Column("planned_at", sa.DateTime(), nullable=True),
        "started_at": sa.Column("started_at", sa.DateTime(), nullable=True),
        "status": sa.Column("status", sa.String(20), nullable=True, server_default="PLANNED"),
        "actual_minutes": sa.Column("actual_minutes", sa.Integer(), nullable=True),
        "strategy": sa.Column("strategy", sa.String(20), nullable=True),
        "executed": sa.Column("executed", sa.Boolean(), nullable=True, server_default=sa.false()),
        "adaptation_reason": sa.Column("adaptation_reason", sa.Text(), nullable=True),
        "is_conditional": sa.Column("is_conditional", sa.Boolean(), nullable=True, server_default=sa.false()),
        "decision_after": sa.Column("decision_after", sa.Boolean(), nullable=True, server_default=sa.false()),
        "execution_order": sa.Column("execution_order", sa.Float(), nullable=True),
    },
}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for name in existing & EXPECTED_COLUMNS.keys():
        columns = {c["name"] for c in inspector.get_columns(name)}
        missing = set(EXPECTED_COLUMNS[name]) - columns - set(ADDITIONS.get(name, {}))
        if missing:
            raise RuntimeError(f"Baseline incompatível com {name}: colunas ausentes {sorted(missing)}")
    if 'curriculum_item_records' not in existing:
        op.create_table('curriculum_item_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('package_id', sa.String(length=100), nullable=False),
            sa.Column('item_type', sa.String(length=30), nullable=False),
            sa.Column('item_key', sa.String(length=200), nullable=False),
            sa.Column('object_id', sa.Integer(), nullable=True),
            sa.Column('latest_version', sa.String(length=30), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('provenance', sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'item_type', 'item_key')
            )
    if 'curriculum_package_records' not in existing:
        op.create_table('curriculum_package_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('package_id', sa.String(length=100), nullable=False),
            sa.Column('version', sa.String(length=30), nullable=False),
            sa.Column('content_hash', sa.String(length=64), nullable=False),
            sa.Column('content_status', sa.String(length=20), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('imported_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('package_id', 'version')
            )
    if 'students' not in existing:
        op.create_table('students',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
            )
    if 'subjects' not in existing:
        op.create_table('subjects',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
            )
    if 'assessments' not in existing:
        op.create_table('assessments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.Column('start_date', sa.Date(), nullable=False),
            sa.Column('end_date', sa.Date(), nullable=False),
            sa.Column('importance', sa.Float(), nullable=False),
            sa.CheckConstraint('end_date >= start_date'),
            sa.CheckConstraint('importance BETWEEN 0 AND 1'),
            sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subject_id', 'name', 'start_date')
            )
    if 'curriculum_units' not in existing:
        op.create_table('curriculum_units',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subject_id', 'key')
            )
    if 'study_sessions' not in existing:
        op.create_table('study_sessions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('available_minutes', sa.Integer(), nullable=False),
            sa.Column('planned_minutes', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('planned_at', sa.DateTime(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('used_minutes', sa.Integer(), nullable=False),
            sa.Column('actual_minutes', sa.Integer(), nullable=True),
            sa.Column('current_activity_id', sa.Integer(), nullable=True),
            sa.Column('strategy', sa.String(length=20), nullable=True),
            sa.Column('adaptation_reason', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('plan_snapshot', sa.JSON(), nullable=False),
            sa.CheckConstraint('available_minutes > 0'),
            sa.CheckConstraint('planned_minutes <= available_minutes'),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id')
            )
    if 'concepts' not in existing:
        op.create_table('concepts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.Column('unit_id', sa.Integer(), nullable=True),
            sa.Column('parent_concept_id', sa.Integer(), nullable=True),
            sa.Column('slug', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('difficulty', sa.Float(), nullable=False),
            sa.Column('importance', sa.Float(), nullable=False),
            sa.Column('estimated_minutes', sa.Integer(), nullable=False),
            sa.Column('learning_objectives', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('difficulty BETWEEN 0 AND 1'),
            sa.CheckConstraint('estimated_minutes > 0'),
            sa.CheckConstraint('importance BETWEEN 0 AND 1'),
            sa.ForeignKeyConstraint(['parent_concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
            sa.ForeignKeyConstraint(['unit_id'], ['curriculum_units.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subject_id', 'slug')
            )
    if 'ix_concepts_subject_id' not in {i["name"] for i in sa.inspect(bind).get_indexes('concepts')}:
        op.create_index('ix_concepts_subject_id', 'concepts', ['subject_id'], unique=False)
    if 'assessment_concepts' not in existing:
        op.create_table('assessment_concepts',
            sa.Column('assessment_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('weight', sa.Float(), nullable=False),
            sa.CheckConstraint('weight > 0 AND weight <= 1'),
            sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.PrimaryKeyConstraint('assessment_id', 'concept_id')
            )
    if 'concept_dependencies' not in existing:
        op.create_table('concept_dependencies',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('prerequisite_concept_id', sa.Integer(), nullable=False),
            sa.Column('dependency_strength', sa.Float(), nullable=False),
            sa.Column('is_essential', sa.Boolean(), nullable=False),
            sa.CheckConstraint('concept_id != prerequisite_concept_id'),
            sa.CheckConstraint('dependency_strength > 0 AND dependency_strength <= 1'),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['prerequisite_concept_id'], ['concepts.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('concept_id', 'prerequisite_concept_id')
            )
    if 'curriculum_explanations' not in existing:
        op.create_table('curriculum_explanations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(length=100), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subject_id', 'key')
            )
    if 'exercises' not in existing:
        op.create_table('exercises',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('slug', sa.String(length=120), nullable=False),
            sa.Column('exercise_type', sa.String(length=30), nullable=False),
            sa.Column('prompt', sa.Text(), nullable=False),
            sa.Column('options', sa.JSON(), nullable=True),
            sa.Column('answer_spec', sa.JSON(), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('difficulty', sa.Float(), nullable=False),
            sa.Column('origin_type', sa.String(length=40), nullable=True),
            sa.Column('provenance', sa.JSON(), nullable=True),
            sa.Column('error_map', sa.JSON(), nullable=False),
            sa.CheckConstraint('difficulty BETWEEN 0 AND 1'),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug')
            )
    if 'ix_exercises_concept_id' not in {i["name"] for i in sa.inspect(bind).get_indexes('exercises')}:
        op.create_index('ix_exercises_concept_id', 'exercises', ['concept_id'], unique=False)
    if 'review_schedules' not in existing:
        op.create_table('review_schedules',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('stage', sa.Integer(), nullable=False),
            sa.Column('due_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('stage >= 0'),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'concept_id')
            )
    if 'ix_review_schedules_due_at' not in {i["name"] for i in sa.inspect(bind).get_indexes('review_schedules')}:
        op.create_index('ix_review_schedules_due_at', 'review_schedules', ['due_at'], unique=False)
    if 'student_concept_states' not in existing:
        op.create_table('student_concept_states',
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=False),
            sa.Column('mastery', sa.Float(), nullable=True),
            sa.Column('retention', sa.Float(), nullable=False),
            sa.Column('retention_calculated_at', sa.DateTime(), nullable=True),
            sa.Column('self_confidence', sa.Float(), nullable=True),
            sa.Column('evidence_confidence', sa.Float(), nullable=False),
            sa.Column('evidence_count', sa.Integer(), nullable=False),
            sa.Column('delayed_evidence_count', sa.Integer(), nullable=False),
            sa.Column('stability_days', sa.Float(), nullable=False),
            sa.Column('times_seen', sa.Integer(), nullable=False),
            sa.Column('times_attempted', sa.Integer(), nullable=False),
            sa.Column('times_correct', sa.Integer(), nullable=False),
            sa.Column('independent_correct', sa.Integer(), nullable=False),
            sa.Column('last_seen_at', sa.DateTime(), nullable=True),
            sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
            sa.Column('last_correct_at', sa.DateTime(), nullable=True),
            sa.Column('last_independent_at', sa.DateTime(), nullable=True),
            sa.Column('difficulty_success_rate', sa.Float(), nullable=False),
            sa.Column('difficulty_attempt_weight', sa.Float(), nullable=False),
            sa.Column('next_review_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.CheckConstraint('evidence_confidence BETWEEN 0 AND 1'),
            sa.CheckConstraint('evidence_count >= 0'),
            sa.CheckConstraint('mastery IS NULL OR mastery BETWEEN 0 AND 1'),
            sa.CheckConstraint('retention BETWEEN 0 AND 1'),
            sa.CheckConstraint('self_confidence IS NULL OR self_confidence BETWEEN 0 AND 1'),
            sa.CheckConstraint('stability_days > 0'),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('student_id', 'concept_id')
            )
    if 'session_activities' not in existing:
        op.create_table('session_activities',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=True),
            sa.Column('exercise_id', sa.Integer(), nullable=True),
            sa.Column('position', sa.Integer(), nullable=False),
            sa.Column('block_index', sa.Integer(), nullable=True),
            sa.Column('activity_type', sa.String(length=30), nullable=False),
            sa.Column('estimated_minutes', sa.Integer(), nullable=False),
            sa.Column('instructions', sa.Text(), nullable=False),
            sa.Column('planned_at', sa.DateTime(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('actual_minutes', sa.Integer(), nullable=True),
            sa.Column('strategy', sa.String(length=20), nullable=True),
            sa.Column('executed', sa.Boolean(), nullable=False),
            sa.Column('adaptation_reason', sa.Text(), nullable=True),
            sa.Column('is_conditional', sa.Boolean(), nullable=False),
            sa.Column('decision_after', sa.Boolean(), nullable=False),
            sa.Column('execution_order', sa.Float(), nullable=True),
            sa.CheckConstraint('estimated_minutes > 0'),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ),
            sa.ForeignKeyConstraint(['session_id'], ['study_sessions.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('session_id', 'position')
            )
    if 'exercise_attempts' not in existing:
        op.create_table('exercise_attempts',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('exercise_id', sa.Integer(), nullable=False),
            sa.Column('activity_id', sa.Integer(), nullable=True),
            sa.Column('attempt_kind', sa.String(length=30), nullable=False),
            sa.Column('answer', sa.JSON(), nullable=False),
            sa.Column('correct', sa.Boolean(), nullable=False),
            sa.Column('score', sa.Float(), nullable=False),
            sa.Column('error_type', sa.String(length=30), nullable=True),
            sa.Column('concepts_involved', sa.JSON(), nullable=False),
            sa.Column('evaluator_confidence', sa.Float(), nullable=False),
            sa.Column('feedback', sa.Text(), nullable=False),
            sa.Column('hints_used', sa.Integer(), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False),
            sa.Column('response_time', sa.Float(), nullable=False),
            sa.Column('self_confidence', sa.Float(), nullable=True),
            sa.Column('is_independent', sa.Boolean(), nullable=False),
            sa.Column('occurred_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint('attempt_number > 0'),
            sa.CheckConstraint('hints_used >= 0'),
            sa.CheckConstraint('response_time >= 0'),
            sa.CheckConstraint('score BETWEEN 0 AND 1'),
            sa.ForeignKeyConstraint(['activity_id'], ['session_activities.id'], ),
            sa.ForeignKeyConstraint(['exercise_id'], ['exercises.id'], ),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'exercise_id', 'attempt_number')
            )
    if 'ix_exercise_attempts_occurred_at' not in {i["name"] for i in sa.inspect(bind).get_indexes('exercise_attempts')}:
        op.create_index('ix_exercise_attempts_occurred_at', 'exercise_attempts', ['occurred_at'], unique=False)
    if 'learning_events' not in existing:
        op.create_table('learning_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('concept_id', sa.Integer(), nullable=True),
            sa.Column('attempt_id', sa.Integer(), nullable=True),
            sa.Column('event_type', sa.String(length=40), nullable=False),
            sa.Column('payload', sa.JSON(), nullable=False),
            sa.Column('occurred_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['attempt_id'], ['exercise_attempts.id'], ),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
            sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('attempt_id')
            )
    for table, additions in ADDITIONS.items():
        columns = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for name, column in additions.items():
            if name not in columns:
                if bind.dialect.name == "sqlite" and column.foreign_keys:
                    # SQLite can add a nullable inline reference without rebuilding data.
                    target = next(iter(column.foreign_keys)).target_fullname.split(".")
                    op.execute(sa.text(
                        f'ALTER TABLE "{table}" ADD COLUMN "{name}" INTEGER '
                        f'REFERENCES "{target[0]}" ("{target[1]}")'))
                else:
                    op.add_column(table, column)


def downgrade():
    raise RuntimeError("A baseline não permite downgrade destrutivo; restaure um backup validado")
