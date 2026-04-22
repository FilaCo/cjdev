package ddd_cj.core

public abstract class Entity<IdT> <: Equatable<Entity<IdT>> where IdT <: Equatable<IdT> {
    public prop id: IdT

    public operator func ==(other: Entity<IdT>): Bool {
        id == other.id
    }

    public operator func !=(other: Entity<IdT>): Bool {
        !(this == other)
    }
}
