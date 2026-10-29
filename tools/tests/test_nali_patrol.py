"""Synthetic castle patrol fixtures; no original game content is committed."""

import hashlib
import json

import pytest

from ue1_converter.nali_patrol import prepare, source_patrol
from ue1_converter.t3d import T3DError, parse_t3d


def fixture(*, second_tag='p2', closing_tag='P1', order='Patroling'):
    return parse_t3d(f'''Begin Map
Begin Actor Class=PatrolPoint Name=SameName
Tag="P1"
Nextpatrol="{second_tag}"
Location=(X=1,Y=2,Z=3)
PauseTime=1.0
PatrolAnim="Cough"
End Actor
Begin Actor Class=Decoration Name=SameName
End Actor
Begin Actor Class=Nali Name=Nali0
Orders="{order}"
OrderTag="p1"
Location=(X=3,Y=4,Z=5)
End Actor
Begin Actor Class=PatrolPoint Name=SameName
Tag="P2"
Nextpatrol="{closing_tag}"
Location=(X=6,Y=7,Z=8)
End Actor
End Map''')


def test_patrol_links_use_case_insensitive_tags_not_repeated_actor_names():
    result = source_patrol(fixture())
    assert result['route_source_actor_indices'] == [0, 3]
    assert result['nali']['source_actor_index'] == 2
    assert [p['source_name'] for p in result['points']] == ['SameName', 'SameName']
    assert result['points'][0]['pause_raw'] == '1.0'
    assert result['points'][0]['patrol_anim'] == 'Cough'
    assert result['points'][1]['pause_seconds'] is None


@pytest.mark.parametrize('change, expected', [
    (dict(second_tag='missing'), 'broken patrol link'),
    (dict(closing_tag='P2'), 'one complete loop'),
    (dict(order='Roaming'), 'not ordered to Patroling'),
])
def test_broken_or_nonpatrol_source_is_rejected(change, expected):
    with pytest.raises((ValueError, T3DError), match=expected):
        source_patrol(fixture(**change))


def test_duplicate_case_insensitive_tags_are_rejected():
    source = fixture().source_text.replace('Tag="P2"', 'Tag="p1"')
    with pytest.raises(ValueError, match='ambiguous patrol tag'):
        source_patrol(parse_t3d(source))


def test_prepare_checks_both_input_hashes_and_refuses_overwrite(tmp_path):
    source = tmp_path / 'Unreal.t3d'; source.write_text(fixture().source_text)
    package = tmp_path / 'Unreal.unr'; package.write_bytes(b'synthetic map package')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    plan = tmp_path / 'Unreal.intro.json'
    data = dict(source_file=str(source), source_sha256=digest(source),
                package_file=str(package), package_sha256=digest(package))
    plan.write_text(json.dumps(data))
    output = tmp_path / 'patrol'
    report = prepare(plan, output)
    assert json.loads((output / 'Nali0_patrol_ue5.json').read_text()) == report
    with pytest.raises(FileExistsError):
        prepare(plan, output)
    package.write_bytes(b'changed')
    with pytest.raises(ValueError, match='provenance'):
        prepare(plan, tmp_path / 'blocked')
    assert not (tmp_path / 'blocked').exists()
