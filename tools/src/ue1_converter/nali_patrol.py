"""Prepare the castle Nali's source patrol links without inventing navigation."""

import argparse
import hashlib
import json
from pathlib import Path

from .t3d import T3DError, number, parse_struct, parse_t3d


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token(value: str | None) -> str | None:
    if value is None:
        return None
    return value[1:-1] if len(value) >= 2 and value[0] == value[-1] == '"' else value


def _location(actor) -> list[float]:
    raw = actor.property('Location')
    if raw is None:
        raise T3DError('patrol actor has no Location', actor.line)
    fields = parse_struct(raw, actor.line)
    values = {field.name: number(field.value, field.line) for field in fields}
    if set(values) != {'X', 'Y', 'Z'} or len(fields) != 3:
        raise T3DError('patrol Location requires X, Y and Z', actor.line)
    return [values[axis] for axis in ('X', 'Y', 'Z')]


def source_patrol(document):
    """Resolve unique source tags while retaining actor indices and raw properties."""
    actors = list(enumerate(document.actors))
    nalis = [(index, actor) for index, actor in actors
             if actor.attribute('Class') == 'Nali' and actor.attribute('Name') == 'Nali0']
    if len(nalis) != 1:
        raise ValueError(f'expected one source Nali0, found {len(nalis)}')
    index, actor = nalis[0]
    if _token(actor.property('Orders')) != 'Patroling':
        raise T3DError('Nali0 is not ordered to Patroling', actor.line)
    first_tag = _token(actor.property('OrderTag'))
    if not first_tag:
        raise T3DError('Nali0 has no OrderTag', actor.line)
    nali = dict(source_actor_index=index, source_name=actor.attribute('Name'),
                location=_location(actor), orders_raw=actor.property('Orders'),
                order_tag_raw=actor.property('OrderTag'),
                attitude_raw=actor.property('AttitudeToPlayer'))
    points = []
    for point_index, point in actors:
        if point.attribute('Class') != 'PatrolPoint':
            continue
        tag = _token(point.property('Tag'))
        next_tag = _token(point.property('Nextpatrol'))
        if not tag or not next_tag:
            raise T3DError('PatrolPoint requires Tag and Nextpatrol', point.line)
        pause_raw = point.property('PauseTime')
        pause = number(pause_raw, point.line) if pause_raw is not None else None
        if pause is not None and pause < 0:
            raise T3DError('negative patrol pause', point.line)
        points.append(dict(source_actor_index=point_index, source_name=point.attribute('Name'),
                           tag=tag, tag_raw=point.property('Tag'), next_tag=next_tag,
                           next_tag_raw=point.property('Nextpatrol'), location=_location(point),
                           rotation_raw=point.property('Rotation'), pause_seconds=pause,
                           pause_raw=pause_raw, patrol_anim=_token(point.property('PatrolAnim')),
                           patrol_anim_raw=point.property('PatrolAnim'),
                           num_anims_raw=point.property('numAnims'),
                           patrol_sound_raw=point.property('PatrolSound')))
    by_tag = {}
    for point in points:
        key = point['tag'].casefold()  # UE1 names are case-insensitive.
        if key in by_tag:
            raise ValueError(f'ambiguous patrol tag {point["tag"]!r}')
        by_tag[key] = point
    route, visited, tag = [], set(), first_tag
    while tag.casefold() not in visited:
        key = tag.casefold()
        if key not in by_tag:
            raise ValueError(f'broken patrol link to {tag!r}')
        point = by_tag[key]
        route.append(point['source_actor_index'])
        visited.add(key)
        tag = point['next_tag']
    if tag.casefold() != first_tag.casefold() or len(visited) != len(points):
        raise ValueError('patrol links do not form one complete loop')
    return dict(schema='nali-source-patrol-v1', nali=nali, points=points,
                route_source_actor_indices=route,
                limitations=['T3D values and links only; no UE1 pathfinding, class defaults, collision, speed or runtime timing',
                             'PatrolPoint animation and PauseTime behavior requires native-script verification',
                             'No modern Nali rig, UE5 asset or live actor is created'])


def prepare(intro_plan: Path, output_dir: Path):
    if output_dir.exists():
        raise FileExistsError('Nali patrol output must be a new directory')
    plan = json.loads(intro_plan.read_text(encoding='utf-8'))
    source = Path(plan['source_file'])
    package = Path(plan['package_file'])
    if _digest(source) != plan['source_sha256'] or _digest(package) != plan['package_sha256']:
        raise ValueError('intro source or original package differs from checked provenance')
    report = source_patrol(parse_t3d(source.read_text(encoding='utf-8')))
    report.update(source_file=str(source.resolve()), source_sha256=plan['source_sha256'],
                  package_file=str(package.resolve()), package_sha256=plan['package_sha256'],
                  intro_plan=str(intro_plan.resolve()), intro_plan_sha256=_digest(intro_plan))
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'Nali0_patrol_ue5.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('intro_plan', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.intro_plan, args.output_dir)
    except (OSError, KeyError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(dict(nali=report['nali'], route_source_actor_indices=report['route_source_actor_indices']), indent=2))


if __name__ == '__main__':
    main()
